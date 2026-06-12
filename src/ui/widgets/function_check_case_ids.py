from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from src.app.runtime_tools import get_app_root


_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_REL_NS = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_PREFERRED_FILE_NAME = "对标功能点检用例.xlsx"
_CASE_DIR_NAME = "行车功能点检caseid"
_DETAIL_HEADERS = (
    "测试类型",
    "测试项目",
    "测试场景描述",
    "测试道路",
    "初始条件",
    "测试步骤",
    "测试记录",
)


@dataclass(frozen=True)
class FunctionCheckCaseRecord:
    case_id: str
    sheet_name: str
    details: Sequence[Tuple[str, str]] = ()

    def detail_text(self) -> str:
        rows = [("来源", self.sheet_name), *self.details]
        return "\n\n".join(f"{label}：{value}" for label, value in rows if value)


@dataclass(frozen=True)
class FunctionCheckCaseIdCatalog:
    records: Sequence[FunctionCheckCaseRecord]
    source_file: Path | None = None

    @property
    def case_ids(self) -> Sequence[str]:
        return [record.case_id for record in self.records]

    def search(self, text: str, limit: int = 200) -> List[str]:
        query = text.strip().lower()
        case_ids = list(dict.fromkeys(record.case_id for record in self.records if record.case_id))
        if not query:
            return case_ids[:limit]

        starts = [case_id for case_id in case_ids if case_id.lower().startswith(query)]
        contains = [
            case_id
            for case_id in case_ids
            if query in case_id.lower() and not case_id.lower().startswith(query)
        ]
        return (starts + contains)[:limit]

    def get(self, case_id: str) -> FunctionCheckCaseRecord | None:
        normalized = case_id.strip().lower()
        if not normalized:
            return None
        return next(
            (record for record in self.records if record.case_id.lower() == normalized),
            None,
        )


_CATALOG_CACHE: FunctionCheckCaseIdCatalog | None = None


def load_function_check_case_id_catalog() -> FunctionCheckCaseIdCatalog:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    files = _find_case_id_files()
    if not files:
        _CATALOG_CACHE = FunctionCheckCaseIdCatalog(records=[])
        return _CATALOG_CACHE

    source_file = files[0]
    _CATALOG_CACHE = FunctionCheckCaseIdCatalog(
        records=_extract_records_from_xlsx(source_file),
        source_file=source_file,
    )
    return _CATALOG_CACHE


def _find_case_id_files() -> List[Path]:
    roots: List[Path] = []
    cwd = Path.cwd()
    app_root = get_app_root()
    for root in [app_root, app_root / "_internal", cwd, *cwd.parents, Path(__file__).resolve().parents[3]]:
        if root not in roots:
            roots.append(root)

    files: Dict[Path, None] = {}
    for root in roots:
        case_dir = root / "caseid" / _CASE_DIR_NAME
        if case_dir.exists():
            for path in case_dir.glob("*.xlsx"):
                if path.name.startswith("~$"):
                    continue
                files[path.resolve()] = None

    return sorted(
        files.keys(),
        key=lambda path: (path.name != _PREFERRED_FILE_NAME, path.name),
    )


def _extract_records_from_xlsx(path: Path) -> List[FunctionCheckCaseRecord]:
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheets = _read_sheets(archive)
        records: List[FunctionCheckCaseRecord] = []
        for sheet_name, sheet_path in sheets:
            records.extend(_extract_sheet_records(archive, sheet_path, sheet_name, shared_strings))
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
        sheet_path = posixpath.normpath(sheet_path)
        sheets.append((sheet.attrib.get("name", ""), sheet_path))
    return sheets


def _extract_sheet_records(
    archive: ZipFile,
    sheet_path: str,
    sheet_name: str,
    shared_strings: Sequence[str],
) -> Iterable[FunctionCheckCaseRecord]:
    headers: Dict[int, str] = {}
    case_id_column: int | None = None
    with archive.open(sheet_path) as stream:
        for _event, row_element in ET.iterparse(stream, events=("end",)):
            if not row_element.tag.endswith("}row"):
                continue

            row_values = {
                _column_index(cell.attrib.get("r", "A1")): _cell_text(cell, shared_strings)
                for cell in row_element.findall("a:c", _NS)
            }

            if case_id_column is None:
                for column_index, value in row_values.items():
                    if _is_case_id_header(value):
                        headers = row_values
                        case_id_column = column_index
                        break
                row_element.clear()
                continue

            case_id = row_values.get(case_id_column, "").strip()
            if case_id and not _is_case_id_header(case_id):
                yield FunctionCheckCaseRecord(
                    case_id=case_id,
                    sheet_name=sheet_name,
                    details=_row_details(row_values, headers),
                )

            row_element.clear()


def _row_details(row_values: Dict[int, str], headers: Dict[int, str]) -> Tuple[Tuple[str, str], ...]:
    details: List[Tuple[str, str]] = []
    allowed_headers = {_normalize_header(header) for header in _DETAIL_HEADERS}
    for column_index in sorted(headers):
        header = headers.get(column_index, "").strip()
        value = row_values.get(column_index, "").strip()
        if not header or not value:
            continue
        if _is_case_id_header(header):
            continue
        if _normalize_header(header) in allowed_headers:
            details.append((header, value))
    return tuple(details)


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
    return _normalize_header(value) == "caseid"


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _column_index(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + ord(character.upper()) - 64
    return index - 1
