"""Read-only access to the part datasheet XLSX.

DB 업무 데이터는 `production` 스키마에만 두고, 부품 카탈로그는 이
XLSX 가 원본이고, MainServer 와 불량대책서 생성기가 함께 읽는다. 파서를 양쪽에 두면
시트 구조가 바뀔 때 두 군데를 고쳐야 하므로 여기 한 곳에 둔다.

서버 런타임에 openpyxl 을 넣지 않는다. zipfile + ElementTree 로만 읽는다.

시트는 부품 하나가 한 행이고, 같은 `부품 타입` 이면 서로 대체 후보다. 보드당 수량과
슬롯 배치는 여기 없다 - `production.product_slots` 가 갖고 있다.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
DATASHEET = ROOT / "data" / "semiconductor_assembly_quality_datasheet_2026-08-18.xlsx"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

PARTS_SHEET, PARTS_HEADER_ROW = "Components", 4
CHECKLIST_SHEET, CHECKLIST_HEADER_ROW = "Checklist", 3
COMMON = "공통"

# 시트 열은 한글이고 API 키는 영문이다. 옮기는 자리를 여기 하나로 둔다.
PART_COLUMNS = {
    "부품 타입": "part_category",
    "제조사 P/N (MPN)": "mpn",
    "핵심 정격": "spec",
    "공급사": "supplier",
    "단가 (USD)": "unit_price",
    "가격 기준 수량": "price_basis",
    "가격 확인일": "price_checked_at",
}
CHECKLIST_COLUMNS = {
    "부품 타입": "part_category",
    "입고 검사": "incoming_inspection",
    "조립/보관 관리": "assembly_control",
    "기능·신뢰성 검사": "reliability_test",
    "이상 시 조치": "action_on_anomaly",
}
GATE_KEYS = ("incoming_inspection", "assembly_control",
             "reliability_test", "action_on_anomaly")


class DatasheetUnavailable(RuntimeError):
    pass


class DatasheetIntegrityError(RuntimeError):
    pass


def _column_index(reference: str) -> int:
    result = 0
    for char in re.match(r"[A-Z]+", reference).group(0):
        result = result * 26 + ord(char) - 64
    return result - 1


def _sheet_rows(path: Path, sheet_name: str) -> list[list[object]]:
    """Read displayed cell values from one XLSX sheet using stdlib OOXML."""
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        relationships = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships.findall(f"{{{REL_NS}}}Relationship")
        }
        relationship_id = None
        for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
            if sheet.attrib["name"] == sheet_name:
                relationship_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
                break
        if relationship_id is None:
            raise DatasheetUnavailable(f"sheet not found: {sheet_name}")

        target = targets[relationship_id].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheet = ET.fromstring(book.read(target))

        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(item.itertext()) for item in strings]

        result = []
        for row in sheet.findall(f".//{{{MAIN_NS}}}row"):
            values: dict[int, object] = {}
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                index = _column_index(cell.attrib["r"])
                cell_type = cell.attrib.get("t")
                value = cell.find(f"{{{MAIN_NS}}}v")
                if cell_type == "inlineStr":
                    inline = cell.find(f"{{{MAIN_NS}}}is")
                    values[index] = "" if inline is None else "".join(inline.itertext())
                elif value is None:
                    values[index] = None
                elif cell_type == "s":
                    values[index] = shared[int(value.text)]
                elif cell_type == "b":
                    values[index] = value.text == "1"
                else:
                    raw = value.text
                    try:
                        values[index] = float(raw) if "." in raw else int(raw)
                    except (TypeError, ValueError):
                        values[index] = raw
            width = max(values, default=-1) + 1
            result.append([values.get(index) for index in range(width)])
        return result


def _table(path: Path, sheet: str, header_row: int,
           columns: dict[str, str]) -> list[dict[str, object]]:
    """헤더 행의 한글 열 이름을 영문 키로 옮겨 행 목록을 만든다."""
    rows = _sheet_rows(path, sheet)
    if len(rows) < header_row:
        raise DatasheetUnavailable(f"{sheet}: header row {header_row} is missing")
    headers = [str(value).strip() if value is not None else ""
               for value in rows[header_row - 1]]
    missing = [name for name in columns if name not in headers]
    if missing:
        raise DatasheetUnavailable(f"{sheet}: 열을 찾지 못했다 {missing}")

    records = []
    for row in rows[header_row:]:
        if not any(value not in (None, "") for value in row):
            continue
        record = {}
        for index, header in enumerate(headers):
            key = columns.get(header)
            if key is None:
                continue
            record[key] = row[index] if index < len(row) else None
        records.append(record)
    return records


def _required_text(row: dict[str, object], key: str, label: str) -> str:
    value = row[key]
    if not isinstance(value, str) or not value.strip():
        raise DatasheetIntegrityError(f"{label}: {key} must be nonblank text")
    return value.strip()


def load_parts(path: Path) -> dict[str, list[dict[str, object]]]:
    """부품 타입 → 부품 목록. 같은 타입이면 서로 대체 후보다."""
    by_category: dict[str, list[dict[str, object]]] = {}
    seen = set()
    for index, row in enumerate(
            _table(path, PARTS_SHEET, PARTS_HEADER_ROW, PART_COLUMNS), 1):
        label = f"{PARTS_SHEET} data row {index}"
        category = _required_text(row, "part_category", label)
        mpn = _required_text(row, "mpn", label)
        spec = _required_text(row, "spec", label)
        supplier = _required_text(row, "supplier", label)
        price_basis = _required_text(row, "price_basis", label)
        price_checked_at = _required_text(row, "price_checked_at", label)
        price = row["unit_price"]
        if (isinstance(price, bool) or not isinstance(price, (int, float))
                or not math.isfinite(float(price)) or price <= 0):
            raise DatasheetIntegrityError(
                f"{label}: unit_price must be a positive number")
        try:
            checked_on = date.fromisoformat(price_checked_at)
        except ValueError as error:
            raise DatasheetIntegrityError(
                f"{label}: price_checked_at must use YYYY-MM-DD") from error
        if checked_on.isoformat() != price_checked_at:
            raise DatasheetIntegrityError(
                f"{label}: price_checked_at must use YYYY-MM-DD")
        unique_key = (category, mpn)
        if unique_key in seen:
            raise DatasheetIntegrityError(
                f"{label}: duplicate part_category and mpn: {category}, {mpn}")
        seen.add(unique_key)
        by_category.setdefault(category, []).append({
            "mpn": mpn,
            "spec": spec,
            "supplier": supplier,
            "unit_price": round(float(price), 2),
            "price_basis": price_basis,
            "price_checked_at": price_checked_at,
        })
    return by_category


def load_checklist(path: Path) -> dict[str, dict[str, str]]:
    """부품 타입 → 품질 게이트. '공통' 행을 각 타입 앞에 붙여 둔다."""
    rows = _table(path, CHECKLIST_SHEET, CHECKLIST_HEADER_ROW, CHECKLIST_COLUMNS)
    common = {}
    gates: dict[str, dict[str, str]] = {}
    seen = set()
    for index, row in enumerate(rows, 1):
        label = f"{CHECKLIST_SHEET} data row {index}"
        category = _required_text(row, "part_category", label)
        if category in seen:
            raise DatasheetIntegrityError(
                f"{label}: duplicate part_category: {category}")
        seen.add(category)
        values = {key: _required_text(row, key, label) for key in GATE_KEYS}
        if category == COMMON:
            common = values
        else:
            gates[category] = values

    if not common:
        raise DatasheetIntegrityError(f"{CHECKLIST_SHEET}: {COMMON} row is required")

    merged = {COMMON: common}
    for category, values in gates.items():
        merged[category] = {
            key: "\n".join(part for part in (common.get(key, ""), values[key]) if part)
            for key in GATE_KEYS
        }
    return merged


_lock = threading.Lock()
_cache: tuple[Path, tuple[int, int], dict] | None = None


def catalog(path: Path | None = None) -> dict:
    """적재된 데이터시트. 파일이 바뀌었을 때만 다시 읽는다.

    담당자가 시트를 고치면 서버 재시작 없이 다음 요청에서 반영된다.
    """
    global _cache
    path = Path(path) if path else DATASHEET
    try:
        status = path.stat()
    except OSError as error:
        raise DatasheetUnavailable(f"datasheet not found: {path}") from error
    stamp = (status.st_mtime_ns, status.st_size)

    with _lock:
        if _cache is not None and _cache[0] == path and _cache[1] == stamp:
            return _cache[2]
        dated = re.search(r"\d{4}-\d{2}-\d{2}", path.name)
        parts = load_parts(path)
        checklist = load_checklist(path)
        checklist_categories = set(checklist) - {COMMON}
        part_categories = set(parts)
        if checklist_categories != part_categories:
            missing_checklist = sorted(part_categories - checklist_categories)
            missing_parts = sorted(checklist_categories - part_categories)
            raise DatasheetIntegrityError(
                "part/checklist category mismatch: "
                f"missing checklist={missing_checklist}, missing parts={missing_parts}")
        loaded = {
            "parts": parts,
            "checklist": checklist,
            "path": path,
            "source_file": path.name,
            "dated_on": dated.group(0) if dated else "",
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        _cache = (path, stamp, loaded)
        return loaded


def candidates(part_category: str, path: Path | None = None) -> list[dict[str, object]]:
    """해당 타입의 부품 후보. 없으면 빈 목록."""
    return catalog(path)["parts"].get(part_category, [])


def selected_candidate(part_category: str, part_name: str,
                       path: Path | None = None) -> dict[str, object]:
    """DB가 선택한 MPN. 카테고리나 MPN 불일치는 잘못된 단가 대신 오류다."""
    rows = candidates(part_category, path)
    chosen = next((row for row in rows if row["mpn"] == part_name), None)
    if chosen is None:
        raise DatasheetIntegrityError(
            f"selected part is missing from datasheet: {part_category}, {part_name}")
    return chosen


def prices(part_category: str, part_name: str = "",
           path: Path | None = None) -> dict[str, object]:
    """타입의 단가 요약. `selected` 는 DB part_name 과 MPN 이 같은 후보다."""
    chosen = (selected_candidate(part_category, part_name, path)["unit_price"]
              if part_name else None)
    rows = [row for row in candidates(part_category, path)
            if row["unit_price"] is not None]
    if not rows:
        return {"unit_price_min": None, "unit_price_max": None,
                "unit_price_selected": None, "candidate_count": 0}
    values = [row["unit_price"] for row in rows]
    return {
        "unit_price_min": min(values),
        "unit_price_max": max(values),
        "unit_price_selected": chosen if part_name else min(values),
        "candidate_count": len(rows),
    }
