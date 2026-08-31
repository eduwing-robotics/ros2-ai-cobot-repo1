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

import psycopg
from psycopg.rows import dict_row

import datasheet
from datasheet import DATASHEET


ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "templates" / "불량대책서_표준양식.xlsx"
OUTPUT_DIR = ROOT / "reports" / "defects"
TOKEN_RE = re.compile(r"\{\{[A-Za-z0-9_]+\}\}")


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


def _catalog_tokens(part_category: str, part_name: str,
                    path: Path) -> dict[str, str]:
    """데이터시트에서 오는 토큰. 조회 키는 부품 타입이다.

    같은 타입의 부품이 곧 서로의 대체 후보라 그룹을 따로 관리하지 않는다.
    `part_name` 은 DB 가 실제로 쓰는 부품이고, 후보 중 MPN 이 같은 행의 단가가
    `unit_price_selected` 가 된다.
    """
    loaded = datasheet.catalog(path)
    rows = loaded["parts"].get(part_category, [])
    gates = (loaded["checklist"].get(part_category)
             or loaded["checklist"].get(datasheet.COMMON, {}))

    if rows:
        def lines(key: str) -> str:
            return "\n".join(_text(row[key]) for row in rows)

        summary = datasheet.prices(part_category, part_name, path)
        tokens = {
            "category_label": part_category,
            "candidate_count": str(len(rows)),
            "manufacturer_part_number": lines("mpn"),
            "key_spec": lines("spec"),
            "supplier": lines("supplier"),
            "unit_price": "\n".join(
                "—" if row["unit_price"] is None else f"${row['unit_price']:,.2f}"
                for row in rows
            ),
            "price_basis": lines("price_basis"),
            "price_checked_at": lines("price_checked_at"),
            "price_range": (
                "—" if summary["unit_price_min"] is None else
                f"${summary['unit_price_min']:,.2f} ~ ${summary['unit_price_max']:,.2f}"
            ),
            "price_selected": (
                "—" if summary["unit_price_selected"] is None else
                f"${summary['unit_price_selected']:,.2f}"
            ),
        }
    else:
        tokens = {
            "category_label": part_category or "—",
            "candidate_count": "0",
            "manufacturer_part_number": "데이터시트 연결 없음",
            "key_spec": "해당 데이터시트 없음",
            "supplier": "—",
            "unit_price": "—",
            "price_basis": "—",
            "price_checked_at": "—",
            "price_range": "—",
            "price_selected": "—",
        }

    for gate in datasheet.GATE_KEYS:
        tokens[gate] = _text(gates.get(gate)) or "—"
    tokens.update({
        "source_file": loaded["source_file"],
        "source_dated_on": loaded["dated_on"] or "—",
        "queried_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return tokens


def build_tokens(rows: list[dict[str, object]], path: Path) -> dict[str, str]:
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
    tokens.update(_catalog_tokens(
        _text(first["part_category"]), _text(first["part_name"]), path))
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


def generate(dsn: str, path: Path, template: Path, output_dir: Path,
             job_id: int | None = None) -> tuple[int, int]:
    datasheet.catalog(path)          # 시트가 없거나 열이 바뀌었으면 여기서 멈춘다
    groups = defaultdict(list)
    for row in load_defects(dsn, job_id):
        groups[(row["job_id"], row["part_id"], row["defect_type"])].append(row)
    created = skipped = 0
    for key, rows in groups.items():
        tokens = build_tokens(rows, path)
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
    loaded = datasheet.catalog(DATASHEET)
    assert len(loaded["parts"]["MLCC"]) == 3
    assert loaded["checklist"]["MLCC"]["incoming_inspection"]
    assert datasheet.prices("MLCC")["unit_price_min"] == 0.09
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
