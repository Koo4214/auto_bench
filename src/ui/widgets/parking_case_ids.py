from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from src.app.runtime_tools import get_app_root


PARKING_SUBJECT_SCENES: Sequence[str] = (
    "科目一",
    "科目二",
    "科目三",
    "科目四",
    "边界性能",
    "泊车功能点检",
    "特殊车位",
)

_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_REL_NS = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True)
class ParkingCaseRecord:
    case_id: str
    subject_scene: str
    source_file: str
    sheet_name: str
    fields: Dict[str, str]

    def detail_text(self) -> str:
        rows = [
            ("Sheet", self.sheet_name),
        ]
        rows.extend((label, value) for label, value in self.fields.items() if label and value)
        return "\n".join(f"{label}: {value}" for label, value in rows if value)


@dataclass(frozen=True)
class ParkingCaseIdCatalog:
    records: Sequence[ParkingCaseRecord]
    source_files: Sequence[Path]

    def search(self, subject_scene: str, text: str, limit: int = 200) -> List[str]:
        query = text.strip().lower()
        case_ids = list(
            dict.fromkeys(
                record.case_id
                for record in self.records
                if record.case_id and _scene_matches(record.subject_scene, subject_scene)
            )
        )
        if not query:
            return case_ids[:limit]

        starts = [case_id for case_id in case_ids if case_id.lower().startswith(query)]
        contains = [
            case_id
            for case_id in case_ids
            if query in case_id.lower() and not case_id.lower().startswith(query)
        ]
        return (starts + contains)[:limit]

    def get(self, case_id: str) -> ParkingCaseRecord | None:
        normalized = case_id.strip().lower()
        if not normalized:
            return None
        return next(
            (record for record in self.records if record.case_id.lower() == normalized),
            None,
        )


_CATALOG_CACHE: ParkingCaseIdCatalog | None = None


def load_parking_case_id_catalog() -> ParkingCaseIdCatalog:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    files = _find_case_id_files()
    records: List[ParkingCaseRecord] = []
    for file_path in files:
        records.extend(_extract_records_from_xlsx(file_path))
    _CATALOG_CACHE = ParkingCaseIdCatalog(records=records, source_files=files)
    return _CATALOG_CACHE


def _find_case_id_files() -> List[Path]:
    roots: List[Path] = []
    cwd = Path.cwd()
    for root in [get_app_root(), cwd, *cwd.parents, Path(__file__).resolve().parents[3]]:
        if root not in roots:
            roots.append(root)

    files: Dict[Path, None] = {}
    for root in roots:
        case_dir = root / "caseid" / "泊车caseID"
        if case_dir.exists():
            for path in case_dir.glob("*.xlsx"):
                if path.name.startswith("~$"):
                    continue
                files[path.resolve()] = None

    return sorted(files.keys(), key=lambda path: path.name)


def _extract_records_from_xlsx(path: Path) -> List[ParkingCaseRecord]:
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        records: List[ParkingCaseRecord] = []
        for sheet_name, sheet_path in _read_sheets(archive):
            records.extend(_extract_sheet_records(archive, sheet_path, path.name, sheet_name, shared_strings))
    return records


def _read_shared_strings(archive: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: List[str] = []
    for item in root.findall("a:si", _NS):
        values.append("".join((text.text or "") for text in item.findall(".//a:t", _NS)))
    return values


def _read_sheets(archive: ZipFile) -> List[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("rel:Relationship", _REL_NS)
    }
    sheets: List[tuple[str, str]] = []
    for sheet in workbook.findall("a:sheets/a:sheet", _NS):
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_targets[rel_id]
        sheet_path = target if target.startswith("xl/") else posixpath.join("xl", target)
        sheets.append((sheet.attrib.get("name", ""), posixpath.normpath(sheet_path)))
    return sheets


def _extract_sheet_records(
    archive: ZipFile,
    sheet_path: str,
    source_file: str,
    sheet_name: str,
    shared_strings: Sequence[str],
) -> Iterable[ParkingCaseRecord]:
    header_row: Dict[int, str] | None = None
    case_id_columns: set[int] = set()
    with archive.open(sheet_path) as stream:
        for _event, row_element in ET.iterparse(stream, events=("end",)):
            if not row_element.tag.endswith("}row"):
                continue

            row_values = {
                _column_index(cell.attrib.get("r", "A1")): _cell_text(cell, shared_strings)
                for cell in row_element.findall("a:c", _NS)
            }

            if not case_id_columns:
                for column_index, value in row_values.items():
                    if _is_case_id_header(value):
                        header_row = row_values
                        case_id_columns.add(column_index)
                        break
                row_element.clear()
                continue

            if header_row is None:
                row_element.clear()
                continue

            for column_index in case_id_columns:
                case_id = row_values.get(column_index, "").strip()
                if not case_id or _is_case_id_header(case_id):
                    continue

                fields = _row_fields(row_values, header_row, column_index)
                subject_scene = _subject_scene(fields, source_file)
                if not subject_scene:
                    continue

                yield ParkingCaseRecord(
                    case_id=case_id,
                    subject_scene=subject_scene,
                    source_file=source_file,
                    sheet_name=sheet_name,
                    fields=fields,
                )

            row_element.clear()


def _row_fields(row_values: Dict[int, str], headers: Dict[int, str], case_id_column: int) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for column_index, value in row_values.items():
        if column_index == case_id_column:
            continue
        value = value.strip()
        if not value:
            continue
        header = headers.get(column_index, "").strip() or f"列{column_index + 1}"
        header = _clean_header(header)
        if _is_case_id_header(header):
            continue
        fields[header] = value
    return fields


def _subject_scene(fields: Dict[str, str], source_file: str) -> str:
    for header, value in fields.items():
        if _normalize_header(header) == "科目场景":
            return _normalize_subject_scene(value)
    return _subject_scene_from_file(source_file)


def _subject_scene_from_file(source_file: str) -> str:
    if "边界性能" in source_file:
        return "边界性能"
    if "功能点检" in source_file:
        return "泊车功能点检"
    if "特殊车位" in source_file:
        return "特殊车位"
    if "避障" in source_file:
        return "科目四"
    return ""


def _normalize_subject_scene(value: str) -> str:
    compact = _normalize_header(value)
    if "科目一" in compact:
        return "科目一"
    if "科目二" in compact:
        return "科目二"
    if "科目三" in compact:
        return "科目三"
    if "科目四" in compact:
        return "科目四"
    if "边界性能" in compact:
        return "边界性能"
    if "功能点检" in compact:
        return "泊车功能点检"
    if "特殊车位" in compact:
        return "特殊车位"
    return value.strip()


def _scene_matches(record_scene: str, selected_scene: str) -> bool:
    if not selected_scene:
        return True
    return _normalize_subject_scene(record_scene) == _normalize_subject_scene(selected_scene)


def _cell_text(cell: ET.Element, shared_strings: Sequence[str]) -> str:
    value = cell.find("a:v", _NS)
    if value is None or value.text is None:
        inline = cell.find("a:is", _NS)
        if inline is None:
            return ""
        return "".join((text.text or "") for text in inline.findall(".//a:t", _NS)).strip()

    text = value.text
    if cell.attrib.get("t") == "s" and text:
        return shared_strings[int(text)].strip()
    return str(text).strip()


def _is_case_id_header(value: str) -> bool:
    compact = _normalize_header(value)
    return "caseid" in compact or ("测试编号" in compact and "case" in compact)


def _clean_header(value: str) -> str:
    return re.sub(r"\s+", " / ", value.strip())


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _column_index(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + ord(character.upper()) - 64
    return index - 1
