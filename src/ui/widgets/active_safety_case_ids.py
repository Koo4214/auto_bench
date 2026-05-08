from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ACTIVE_SAFETY_FUNCTIONS: Sequence[str] = (
    "AEB",
    "FCW",
    "RAEB",
    "MEB",
    "AES",
    "LKA",
    "LDW",
    "IHB",
    "TSR",
    "DSM",
    "DOW",
    "BSD",
    "RTCA",
)

_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_REL_NS = {
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_CELL_REF_RE = re.compile(r"([A-Z]+)(\d+)")
_PREFERRED_FILE_NAME = "自动紧急制动_避让场景case id库_V2.5--长期维护更新 副本.xlsx"


@dataclass(frozen=True)
class ActiveSafetyCaseIdCatalog:
    case_ids: Sequence[str]
    source_file: Path | None = None

    def search(self, function_name: str, text: str, limit: int = 200) -> List[str]:
        prefix = function_name.strip().upper()
        query = text.strip().lower()
        scoped = [
            case_id
            for case_id in self.case_ids
            if not prefix or case_id.upper().startswith(prefix)
        ]
        if not query:
            return scoped[:limit]

        starts = [case_id for case_id in scoped if case_id.lower().startswith(query)]
        contains = [
            case_id
            for case_id in scoped
            if query in case_id.lower() and not case_id.lower().startswith(query)
        ]
        return (starts + contains)[:limit]


_CATALOG_CACHE: ActiveSafetyCaseIdCatalog | None = None


def load_active_safety_case_id_catalog() -> ActiveSafetyCaseIdCatalog:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    files = _find_case_id_files()
    if not files:
        _CATALOG_CACHE = ActiveSafetyCaseIdCatalog(case_ids=[])
        return _CATALOG_CACHE

    source_file = files[0]
    _CATALOG_CACHE = ActiveSafetyCaseIdCatalog(
        case_ids=_extract_case_ids_from_xlsx(source_file),
        source_file=source_file,
    )
    return _CATALOG_CACHE


def _find_case_id_files() -> List[Path]:
    roots: List[Path] = []
    cwd = Path.cwd()
    for root in [cwd, *cwd.parents]:
        if root not in roots:
            roots.append(root)

    files: Dict[Path, None] = {}
    for root in roots:
        case_dir = root / "caseid" / "主动安全caseid"
        if case_dir.exists():
            for path in case_dir.glob("*.xlsx"):
                files[path.resolve()] = None

    return sorted(
        files.keys(),
        key=lambda path: (path.name != _PREFERRED_FILE_NAME, path.name),
    )


def _extract_case_ids_from_xlsx(path: Path) -> List[str]:
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheets = _read_sheet_paths(archive)
        case_ids: List[str] = []
        for sheet_path in sheets:
            case_ids.extend(_extract_sheet_case_ids(archive, sheet_path, shared_strings))
    return sorted(set(case_id for case_id in case_ids if case_id))


def _read_shared_strings(archive: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: List[str] = []
    for item in root.findall("a:si", _NS):
        values.append("".join((text.text or "") for text in item.findall(".//a:t", _NS)))
    return values


def _read_sheet_paths(archive: ZipFile) -> List[str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("rel:Relationship", _REL_NS)
    }
    sheet_paths: List[str] = []
    for sheet in workbook.findall("a:sheets/a:sheet", _NS):
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_targets[rel_id]
        sheet_paths.append(target if target.startswith("xl/") else f"xl/{target}")
    return sheet_paths


def _extract_sheet_case_ids(
    archive: ZipFile,
    sheet_path: str,
    shared_strings: Sequence[str],
) -> Iterable[str]:
    case_id_columns: set[int] = set()
    with archive.open(sheet_path) as stream:
        for _event, row_element in ET.iterparse(stream, events=("end",)):
            if not row_element.tag.endswith("}row"):
                continue

            row_values: Dict[int, str] = {}
            row_formulas: Dict[int, str] = {}
            for cell in row_element.findall("a:c", _NS):
                column_index = _column_index(cell.attrib.get("r", "A1"))
                row_values[column_index] = _cell_text(cell, shared_strings)
                formula = cell.find("a:f", _NS)
                if formula is not None and formula.text:
                    row_formulas[column_index] = formula.text

            for column_index, value in row_values.items():
                if _is_case_id_header(value):
                    case_id_columns.add(column_index)

            for column_index in case_id_columns:
                value = row_values.get(column_index, "")
                if _is_case_id_header(value):
                    continue
                if not value and column_index in row_formulas:
                    value = _evaluate_concat_formula(row_formulas[column_index], row_values)
                if value:
                    yield value

            row_element.clear()


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
    return value.strip().lower().replace(" ", "") in {"caseid", "case_id"}


def _evaluate_concat_formula(formula: str, row_values: Dict[int, str]) -> str:
    parts: List[str] = []
    for raw_part in formula.split("&"):
        part = raw_part.strip()
        if len(part) >= 2 and part[0] == '"' and part[-1] == '"':
            parts.append(part[1:-1])
            continue
        match = _CELL_REF_RE.fullmatch(part)
        if match:
            parts.append(row_values.get(_column_index(match.group(1)), ""))
            continue
        return ""
    return "".join(parts).strip("_")


def _column_index(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + ord(character.upper()) - 64
    return index - 1
