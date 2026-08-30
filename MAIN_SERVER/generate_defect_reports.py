"""Generate immutable XLSX countermeasure reports from production defects."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parent
DATASHEET = ROOT / "data" / "semiconductor_assembly_quality_datasheet_2026-08-18.xlsx"
TEMPLATE = ROOT / "templates" / "불량대책서_표준양식.xlsx"
OUTPUT_DIR = ROOT / "reports" / "defects"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TOKEN_RE = re.compile(r"\{\{[A-Za-z0-9_]+\}\}")


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
            raise ValueError(f"sheet not found: {sheet_name}")

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


def _table(path: Path, sheet: str, header_row: int) -> list[dict[str, object]]:
    rows = _sheet_rows(path, sheet)
    headers = [str(value).strip() if value is not None else ""
               for value in rows[header_row - 1]]
    records = []
    for row in rows[header_row:]:
        if not any(value not in (None, "") for value in row):
            continue
        records.append({
            header: row[index] if index < len(row) else None
            for index, header in enumerate(headers) if header
        })
    return records


def load_catalog(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"datasheet not found: {path}")
    bom = _table(path, "HBM Package Board BOM", 4)
    components = _table(path, "Components", 4)
    checklists = _table(path, "Checklist", 3)
    sources = _table(path, "Sources", 3)
    by_part = {str(row["Mock Part ID"]).strip(): row for row in bom}
    by_group = defaultdict(list)
    for row in components:
        by_group[str(row["Group ID"]).strip()].append(row)
    return {
        "by_part": by_part,
        "by_group": dict(by_group),
        "checklists": checklists,
        "sources": {str(row["Source ID"]).strip(): row for row in sources},
    }


def load_defects(dsn: str, job_id: int | None = None) -> list[dict[str, object]]:
    values = () if job_id is None else (job_id,)
    job_filter = "" if job_id is None else "AND j.job_id = %s"
    sql = f"""
        SELECT j.job_id, j.product_id, j.recipe_version,
               j.requested_at, j.job_started_at, j.job_finished_at,
               u.unit_id, u.inspected_at, u.inspection_image_path,
               ps.slot_code, p.part_id, p.part_name, p.part_category,
               ud.defect_type,
               (SELECT COUNT(*) FROM production.units inspected
                 WHERE inspected.job_id = j.job_id
                   AND inspected.inspection_result IN ('PASS', 'FAIL'))::integer
                   AS inspected_units,
               (SELECT COUNT(*) FROM production.product_slots part_slot
                 WHERE part_slot.product_id = j.product_id
                   AND part_slot.part_id = p.part_id)::integer AS slots_per_unit
        FROM production.unit_defects ud
        JOIN production.units u ON u.unit_id = ud.unit_id
        JOIN production.jobs j ON j.job_id = u.job_id
        JOIN production.product_slots ps ON ps.product_slot_id = ud.product_slot_id
        JOIN production.parts p ON p.part_id = ps.part_id
        WHERE j.job_status = 'COMPLETED'
          AND u.unit_status = 'COMPLETED'
          AND u.inspection_result = 'FAIL'
          {job_filter}
        ORDER BY j.job_id, p.part_id, ud.defect_type, u.unit_id, ps.slot_code
    """
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        return [dict(row) for row in connection.execute(sql, values).fetchall()]


def _text(value: object) -> str:
    return "—" if value in (None, "") else str(value)


def _date(value: object) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else _text(value)


def _catalog_tokens(catalog: dict[str, object], part_id: str,
                    datasheet: Path) -> dict[str, str]:
    part = catalog["by_part"].get(part_id)
    if not part:
        return {
            "group_id": "데이터시트 연결 없음",
            "category_label": "—",
            "candidate_count": "0",
            "candidate_role": "—",
            "alternate_code": "—",
            "manufacturer": "—",
            "manufacturer_part_number": "—",
            "key_spec": "해당 데이터시트 없음",
            "compatibility_status": "—",
            "revalidation_items": "—",
            "defect_relevance": "미평가",
            "source_id": "—",
            "checked_at": "—",
            "incoming_inspection": "—",
            "assembly_control": "—",
            "reliability_test": "—",
            "action_on_anomaly": "—",
            "source_file": datasheet.name,
            "source_dated_on": "—",
            "queried_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    group_id = str(part["Group ID"]).strip()
    category = _text(part.get("Category"))
    candidates = catalog["by_group"].get(group_id, [])
    sources = catalog["sources"]

    def lines(column: str) -> str:
        return "\n".join(_text(row.get(column)) for row in candidates) or "—"

    source_ids = [str(row.get("Source ID") or "").strip() for row in candidates]
    checked = [sources.get(source_id, {}).get("확인일") for source_id in source_ids]
    checklist_rows = [
        row for row in catalog["checklists"]
        if row.get("범주") in ("공통", category)
    ]

    def checklist(column: str) -> str:
        return "\n".join(_text(row.get(column)) for row in checklist_rows) or "—"

    dated = re.search(r"\d{4}-\d{2}-\d{2}", datasheet.name)
    return {
        "group_id": group_id,
        "category_label": category,
        "candidate_count": str(len(candidates)),
        "candidate_role": lines("역할"),
        "alternate_code": lines("대체 #"),
        "manufacturer": lines("제조사"),
        "manufacturer_part_number": lines("제조사 P/N / 모델"),
        "key_spec": lines("핵심 사양·용도"),
        "compatibility_status": lines("상호호환 상태"),
        "revalidation_items": lines("필수 재검증"),
        "defect_relevance": lines("불량 소견 (defect_relevance)"),
        "source_id": "\n".join(_text(value) for value in source_ids) or "—",
        "checked_at": "\n".join(_text(value) for value in checked) or "—",
        "incoming_inspection": checklist("입고 검사"),
        "assembly_control": checklist("조립/보관 관리"),
        "reliability_test": checklist("기능·신뢰성 검사"),
        "action_on_anomaly": checklist("이상 시 조치"),
        "source_file": datasheet.name,
        "source_dated_on": dated.group(0) if dated else "—",
        "queried_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_tokens(rows: list[dict[str, object]], catalog: dict[str, object],
                 datasheet: Path) -> dict[str, str]:
    first = rows[0]
    job_id = int(first["job_id"])
    part_id = str(first["part_id"])
    defect_type = str(first["defect_type"])
    alert_code = f"QA-J{job_id}-{part_id}-{defect_type}"
    inspected_units = int(first["inspected_units"])
    slots_per_unit = int(first["slots_per_unit"])
    inspected = inspected_units * slots_per_unit
    defective = len(rows)
    defect_rate = defective / inspected if inspected else 0
    slot_counts = Counter(str(row["slot_code"]) for row in rows)
    affected_units = len({row["unit_id"] for row in rows})
    start = first["job_started_at"] or first["requested_at"]
    end = first["job_finished_at"] or first["inspected_at"]
    window_days = max(1, ((end - start).days + 1) if start and end else 1)
    evidence = sorted(rows, key=lambda row: (row["unit_id"], row["slot_code"]))
    hotspot = " · ".join(
        f"{slot} {count}건" for slot, count in slot_counts.most_common()
    )
    generated_at = dt.datetime.now().astimezone()

    tokens = {
        "alert_code": alert_code,
        "issued_at": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "assignee": "배정 대기",
        "support_teams": "담당자 입력",
        "alert_status": "ISSUED",
        "due_initial": "담당자 입력",
        "due_cause": "담당자 입력",
        "due_action": "담당자 입력",
        "due_verify": "적용 후 검증",
        "part_id": part_id,
        "part_name": _text(first["part_name"]),
        "defect_type": defect_type,
        "period_start": _date(start),
        "period_end": _date(end),
        "window_days": str(window_days),
        "evaluation_mode": "JOB",
        "source_recipe_version": _text(first["recipe_version"]),
        "threshold_ppm": "미사용",
        "inspected_quantity": str(inspected),
        "defective_quantity": str(defective),
        "defect_ppm": f"{defect_rate * 1_000_000:,.0f}",
        "vs_threshold_ratio": "임계 판정 없음",
        "unit_impact": f"{inspected_units}대 중 {affected_units}대",
        "hotspot": hotspot,
        "trend_vs_prev": "작업 단위 발행",
        "auto_analysis": (
            f"Job {job_id}에서 {part_id} {defect_type} 불량 {defective}건이 확인됐다.\n"
            f"발생 슬롯: {hotspot}.\n"
            "production 확정 기록과 데이터시트만 사용해 자동 생성됐다."
        ),
        "slot_code": "\n".join(slot_counts),
        "count": "\n".join(str(slot_counts[slot]) for slot in slot_counts),
        "slot_rate": "\n".join(
            f"{slot_counts[slot] / max(inspected_units, 1):.2%}"
            for slot in slot_counts
        ),
        "slot_note": "Job 내 슬롯별 발생",
        "unit_id": "\n".join(str(row["unit_id"]) for row in evidence),
        "inspected_at": "\n".join(_date(row["inspected_at"]) for row in evidence),
        "inspection_image_path": "\n".join(
            _text(row["inspection_image_path"]) for row in evidence
        ),
        "week": generated_at.strftime("%G-W%V"),
        "inspected": str(inspected),
        "defective": str(defective),
        "rate": f"{defect_rate:.4%}",
        "vs_threshold": "—",
        "recipe_version": _text(first["recipe_version"]),
        "note": f"Job {job_id} 자동 발행",
        "applied_period": f"{_date(start)} ~ {_date(end)}",
        "change_note": "레시피 변경 내역은 DB에 저장하지 않음",
        "period": f"Job {job_id}",
        "applied_recipe_version": "—",
        "applied_at": "—",
        "root_cause_summary": "담당자 입력",
        "defect_rate": f"{defect_rate:.4%}",
    }
    tokens.update(_catalog_tokens(catalog, part_id, datasheet))
    return tokens


def _safe_filename(value: object) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    if not safe:
        raise ValueError("report filename component is empty")
    return safe


def write_report(template: Path, output: Path, tokens: dict[str, str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    replacements = {
        f"{{{{{key}}}}}": html.escape(_text(value), quote=False)
        for key, value in tokens.items()
    }
    static_replacements = {
        "defect_report.alert_evidence 스냅샷": "production.unit_defects 확정 기록",
        "datastation_part_checklist · part_catalog.quality_checklists.category":
            "데이터시트 Checklist 시트",
    }
    with tempfile.NamedTemporaryFile(
            dir=output.parent, suffix=".tmp", delete=False) as temporary:
        temp_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(template) as source, zipfile.ZipFile(
                temp_path, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename.endswith(".xml"):
                    text = data.decode("utf-8")
                    for old, new in static_replacements.items():
                        text = text.replace(old, new)
                    for old, new in replacements.items():
                        text = text.replace(old, new)
                    text = TOKEN_RE.sub("—", text)
                    data = text.encode("utf-8")
                target.writestr(item, data)
        with zipfile.ZipFile(temp_path) as report:
            if report.testzip() is not None:
                raise RuntimeError("generated workbook is corrupt")
            remaining = b"".join(
                report.read(name) for name in report.namelist()
                if name.endswith(".xml")
            ).decode("utf-8")
            if TOKEN_RE.search(remaining):
                raise RuntimeError("generated workbook contains unresolved tokens")
        os.replace(temp_path, output)
    finally:
        temp_path.unlink(missing_ok=True)


def generate(dsn: str, datasheet: Path, template: Path, output_dir: Path,
             job_id: int | None = None) -> tuple[int, int]:
    catalog = load_catalog(datasheet)
    groups = defaultdict(list)
    for row in load_defects(dsn, job_id):
        groups[(row["job_id"], row["part_id"], row["defect_type"])].append(row)
    created = skipped = 0
    for key, rows in groups.items():
        tokens = build_tokens(rows, catalog, datasheet)
        filename = "QA-J{}-{}-{}.xlsx".format(
            int(key[0]), _safe_filename(key[1]), _safe_filename(key[2])
        )
        output = output_dir / filename
        if output.exists():
            skipped += 1
            continue
        write_report(template, output, tokens)
        print(f"created {output}")
        created += 1
    return created, skipped


def self_check() -> None:
    catalog = load_catalog(DATASHEET)
    assert catalog["by_part"]["CAP"]["Group ID"] == "C-001"
    assert _safe_filename("../CAP") == "CAP"
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "check.xlsx"
        write_report(TEMPLATE, output, {"alert_code": "QA-CHECK"})
        assert output.is_file()
    print("generate_defect_reports self-check passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("MAIN_SERVER_DB_DSN", ""))
    parser.add_argument("--datasheet", type=Path, default=DATASHEET)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.dsn.strip():
        parser.error("--dsn or MAIN_SERVER_DB_DSN is required")
    created, skipped = generate(
        args.dsn, args.datasheet, args.template, args.output_dir, args.job_id
    )
    print(f"reports created={created} skipped={skipped}")


if __name__ == "__main__":
    main()
