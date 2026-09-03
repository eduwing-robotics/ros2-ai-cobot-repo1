"""Generate and email immutable XLSX countermeasure reports for confirmed defects."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import os
import re
import smtplib
import ssl
import stat
import tempfile
import time
import zipfile
from collections import Counter
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

import datasheet
from datasheet import DATASHEET


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
TEMPLATE = ROOT / "templates" / "불량대책서_표준양식.xlsx"
OUTPUT_DIR = ROOT / "reports" / "defects"
DEFAULT_IMAGE_ROOT = REPO_ROOT / "UnityDT" / "Assets" / "StreamingAssets"
TOKEN_RE = re.compile(r"\{\{[A-Za-z0-9_]+\}\}")
IMAGE_MEDIA = {
    "jpeg": "xl/media/image1.jpeg",
    "png": "xl/media/image2.png",
}


def _connect(dsn: str):
    return psycopg.connect(dsn, row_factory=dict_row)


def load_defect_context(dsn: str, unit_defect_id: int) -> list[dict[str, object]]:
    """Return the target defect and same Job/part/type history as of that inspection."""
    sql = """
        WITH target AS (
            SELECT ud.unit_defect_id, ud.unit_id AS target_unit_id,
                   ud.defect_type AS target_defect_type,
                   ps.part_id AS target_part_id,
                   ps.slot_code AS target_slot_code,
                   u.job_id, u.inspected_at AS target_inspected_at,
                   u.inspection_image_path AS target_image_path
            FROM production.unit_defects ud
            JOIN production.units u ON u.unit_id = ud.unit_id
            JOIN production.product_slots ps
              ON ps.product_slot_id = ud.product_slot_id
            WHERE ud.unit_defect_id = %s
              AND u.unit_status = 'COMPLETED'
              AND u.inspection_result = 'FAIL'
        )
        SELECT target.unit_defect_id, target.target_unit_id,
               target.target_slot_code, target.target_inspected_at,
               target.target_image_path,
               j.job_id, j.product_id, j.recipe_version,
               j.requested_at, j.job_started_at,
               u.unit_id, u.inspected_at, u.inspection_image_path,
               ps.slot_code, p.part_id, p.part_name, p.part_category,
               ud.defect_type,
               (SELECT COUNT(*) FROM production.units inspected
                 WHERE inspected.job_id = j.job_id
                   AND inspected.inspection_result IN ('PASS', 'FAIL')
                   AND inspected.inspected_at <= target.target_inspected_at)::integer
                   AS inspected_units,
               (SELECT COUNT(*) FROM production.product_slots part_slot
                 WHERE part_slot.product_id = j.product_id
                   AND part_slot.part_id = p.part_id)::integer AS slots_per_unit
        FROM target
        JOIN production.jobs j ON j.job_id = target.job_id
        JOIN production.unit_defects ud
          ON ud.defect_type = target.target_defect_type
        JOIN production.units u
          ON u.unit_id = ud.unit_id
         AND u.job_id = target.job_id
         AND u.unit_status = 'COMPLETED'
         AND u.inspection_result = 'FAIL'
         AND u.inspected_at <= target.target_inspected_at
        JOIN production.product_slots ps
          ON ps.product_slot_id = ud.product_slot_id
         AND ps.part_id = target.target_part_id
        JOIN production.parts p ON p.part_id = ps.part_id
        ORDER BY u.inspected_at, u.unit_id, ps.slot_code
    """
    with _connect(dsn) as connection:
        return [
            dict(row)
            for row in connection.execute(sql, (unit_defect_id,)).fetchall()
        ]


def _text(value: object) -> str:
    return "—" if value in (None, "") else str(value)


def _date(value: object) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if hasattr(value, "strftime") else _text(value)


def _catalog_tokens(part_category: str, part_name: str,
                    path: Path) -> dict[str, str]:
    """Read the selected component, alternatives and quality gates from the XLSX."""
    loaded = datasheet.catalog(path)
    rows = loaded["parts"].get(part_category, [])
    selected = next((row for row in rows if row["mpn"] == part_name), None)
    alternatives = [row for row in rows if row is not selected]
    gates = (loaded["checklist"].get(part_category)
             or loaded["checklist"].get(datasheet.COMMON, {}))

    def lines(source: list[dict[str, object]], key: str) -> str:
        return "\n".join(_text(row[key]) for row in source) or "—"

    def prices(source: list[dict[str, object]]) -> str:
        return "\n".join(
            "—" if row["unit_price"] is None else f"${row['unit_price']:,.2f}"
            for row in source
        ) or "—"

    def price(row: dict[str, object] | None) -> str:
        return (
            "—" if not row or row["unit_price"] is None
            else f"${row['unit_price']:,.2f}"
        )

    price_values = [row["unit_price"] for row in rows if row["unit_price"] is not None]
    tokens = {
        "category_label": part_category or "—",
        "datasheet_match": "일치" if selected else "불일치 — 담당자 확인 필요",
        "selected_mpn": _text(selected["mpn"]) if selected else "데이터시트 연결 없음",
        "selected_spec": _text(selected["spec"]) if selected else "—",
        "selected_supplier": _text(selected["supplier"]) if selected else "—",
        "selected_unit_price": price(selected),
        "selected_price_basis": _text(selected["price_basis"]) if selected else "—",
        "selected_price_checked_at": (
            _text(selected["price_checked_at"]) if selected else "—"
        ),
        "candidate_count": str(len(alternatives)),
        "manufacturer_part_number": lines(alternatives, "mpn"),
        "key_spec": lines(alternatives, "spec"),
        "supplier": lines(alternatives, "supplier"),
        "unit_price": prices(alternatives),
        "price_basis": lines(alternatives, "price_basis"),
        "price_checked_at": lines(alternatives, "price_checked_at"),
        "price_range": (
            "—" if not price_values else
            f"${min(price_values):,.2f} ~ ${max(price_values):,.2f}"
        ),
        "price_selected": price(selected),
    }
    for gate in datasheet.GATE_KEYS:
        tokens[gate] = _text(gates.get(gate))
    tokens.update({
        "source_file": f"{loaded['source_file']}\nSHA-256: {loaded['source_sha256']}",
        "source_sha256": loaded["source_sha256"],
        "source_dated_on": loaded["dated_on"] or "—",
        "queried_at": dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return tokens


def build_tokens(rows: list[dict[str, object]], path: Path,
                 image: dict[str, object]) -> dict[str, str]:
    if not rows:
        raise RuntimeError("confirmed defect was not found")
    first = rows[0]
    unit_defect_id = int(first["unit_defect_id"])
    job_id = str(first["job_id"])
    target_unit_id = int(first["target_unit_id"])
    part_id = str(first["part_id"])
    defect_type = str(first["defect_type"])
    alert_code = f"QA-D{unit_defect_id}-{part_id}-{defect_type}"
    inspected_units = int(first["inspected_units"])
    slots_per_unit = int(first["slots_per_unit"])
    inspected = inspected_units * slots_per_unit
    defective = len(rows)
    defect_rate = defective / inspected if inspected else 0
    slot_counts = Counter(str(row["slot_code"]) for row in rows)
    affected_units = len({row["unit_id"] for row in rows})
    start = first["job_started_at"] or first["requested_at"]
    end = first["target_inspected_at"]
    window_days = max(1, ((end - start).days + 1) if start and end else 1)
    generated_at = dt.datetime.now().astimezone()
    hotspot = " · ".join(
        f"{slot} {count}건" for slot, count in slot_counts.most_common()
    )

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
        "unit_defect_id": str(unit_defect_id),
        "job_id": job_id,
        "target_unit_id": str(target_unit_id),
        "target_slot_code": str(first["target_slot_code"]),
        "target_inspected_at": _date(end),
        "part_id": part_id,
        "part_name": _text(first["part_name"]),
        "defect_type": defect_type,
        "period_start": _date(start),
        "period_end": _date(end),
        "window_days": str(window_days),
        "evaluation_mode": "발행 시점 누적",
        "source_recipe_version": _text(first["recipe_version"]),
        "inspected_quantity": str(inspected),
        "defective_quantity": str(defective),
        "defect_ppm": f"{defect_rate * 1_000_000:,.0f}",
        "vs_threshold_ratio": "확정 불량 1건",
        "unit_impact": f"{inspected_units}대 중 {affected_units}대",
        "hotspot": hotspot,
        "auto_analysis": (
            f"확정 불량 {unit_defect_id}: Unit {target_unit_id}, "
            f"{first['target_slot_code']} 슬롯에서 {defect_type}이 확인됐다.\n"
            f"발행 시점까지 동일 Job·부품·유형 누적 {defective}건이다.\n"
            "원인은 자동 추정하지 않으며 담당자가 검사 이미지와 품질기준을 확인한다."
        ),
        "slot_code": "\n".join(slot_counts),
        "count": "\n".join(str(slot_counts[slot]) for slot in slot_counts),
        "slot_rate": "\n".join(
            f"{slot_counts[slot] / max(inspected_units, 1):.2%}"
            for slot in slot_counts
        ),
        "slot_note": "발행 시점까지 동일 Job·부품·유형 누적",
        "unit_id": "\n".join(str(row["unit_id"]) for row in rows),
        "inspected_at": "\n".join(_date(row["inspected_at"]) for row in rows),
        "inspection_image_path": str(image["display_path"]),
        "inspection_image_status": str(image["status"]),
        "inspection_image_sha256": str(image["sha256"]),
    }
    tokens.update(_catalog_tokens(
        _text(first["part_category"]), _text(first["part_name"]), path))
    return tokens


def _safe_filename(value: object) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    if not safe:
        raise ValueError("report filename component is empty")
    return safe


def report_path(output_dir: Path, rows: list[dict[str, object]]) -> Path:
    first = rows[0]
    return output_dir / "QA-D{}-{}-{}.xlsx".format(
        int(first["unit_defect_id"]),
        _safe_filename(first["part_id"]),
        _safe_filename(first["defect_type"]),
    )


def load_inspection_image(value: object, root: Path,
                          max_bytes: int) -> dict[str, object]:
    unavailable = {
        "bytes": None,
        "kind": None,
        "display_path": _text(value),
        "status": "검사 이미지 없음",
        "sha256": "—",
    }
    if value in (None, ""):
        return unavailable
    relative = Path(str(value))
    if relative.is_absolute():
        unavailable["status"] = "절대경로 차단"
        return unavailable
    try:
        root = root.resolve(strict=True)
        source = (root / relative).resolve(strict=True)
    except OSError:
        unavailable["status"] = "검사 이미지 파일 없음"
        return unavailable
    if not source.is_relative_to(root) or not source.is_file():
        unavailable["status"] = "허용 경로 밖 이미지 차단"
        return unavailable
    if source.stat().st_size > max_bytes:
        unavailable["status"] = "검사 이미지 크기 상한 초과"
        return unavailable
    content = source.read_bytes()
    if len(content) > max_bytes:
        unavailable["status"] = "검사 이미지 크기 상한 초과"
        return unavailable
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
    elif content.startswith(b"\xff\xd8\xff"):
        kind = "jpeg"
    else:
        unavailable["status"] = "JPEG/PNG 이외 형식 차단"
        return unavailable
    return {
        "bytes": content,
        "kind": kind,
        "display_path": relative.as_posix(),
        "status": "검사 이미지 포함",
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def write_report(template: Path, output: Path, tokens: dict[str, str],
                 image: dict[str, object] | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    replacements = {
        f"{{{{{key}}}}}": html.escape(_text(value), quote=False)
        for key, value in tokens.items()
    }
    image_target = IMAGE_MEDIA.get(str(image.get("kind"))) if image else None
    image_replaced = False
    with tempfile.NamedTemporaryFile(
            dir=output.parent, suffix=".tmp", delete=False) as temporary:
        temp_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(template) as source, zipfile.ZipFile(
                temp_path, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if image_target == item.filename:
                    data = image["bytes"]
                    image_replaced = True
                elif item.filename.endswith(".xml"):
                    text = data.decode("utf-8")
                    for old, new in replacements.items():
                        text = text.replace(old, new)
                    text = TOKEN_RE.sub("—", text)
                    data = text.encode("utf-8")
                target.writestr(item, data)
        if image_target and not image_replaced:
            raise RuntimeError("report template has no inspection image placeholder")
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


def _positive_setting(env: dict[str, str], name: str, default: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _mail_address(value: str, label: str) -> str:
    if not value or "\r" in value or "\n" in value:
        raise ValueError(f"{label} must be a plain email address")
    display, address = parseaddr(value)
    if display or address != value or address.count("@") != 1:
        raise ValueError(f"{label} must be a plain email address")
    local, domain = address.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise ValueError(f"{label} must be a plain email address")
    return address


def load_mail_config(env: dict[str, str] | None = None) -> dict[str, object]:
    env = dict(os.environ if env is None else env)
    security = env.get("DEFECT_MAIL_SECURITY", "ssl").lower()
    if security not in ("ssl", "starttls"):
        raise ValueError("DEFECT_MAIL_SECURITY must be ssl or starttls")
    host = env.get("DEFECT_MAIL_HOST", "").strip()
    if not host or any(char.isspace() for char in host):
        raise ValueError("DEFECT_MAIL_HOST is required")
    port = _positive_setting(
        env, "DEFECT_MAIL_PORT", 465 if security == "ssl" else 587)
    if port > 65535:
        raise ValueError("DEFECT_MAIL_PORT must be at most 65535")
    sender = _mail_address(env.get("DEFECT_MAIL_FROM", "").strip(),
                           "DEFECT_MAIL_FROM")
    recipients = [
        _mail_address(value.strip(), "DEFECT_MAIL_TO")
        for value in env.get("DEFECT_MAIL_TO", "").split(",") if value.strip()
    ]
    if not recipients:
        raise ValueError("DEFECT_MAIL_TO requires at least one address")
    allowed_domains = {
        value.strip().lower()
        for value in env.get("DEFECT_MAIL_ALLOWED_DOMAINS", "").split(",")
        if value.strip()
    }
    if not allowed_domains:
        raise ValueError("DEFECT_MAIL_ALLOWED_DOMAINS is required")
    blocked = [
        address for address in recipients
        if address.rsplit("@", 1)[1].lower() not in allowed_domains
    ]
    if blocked:
        raise ValueError("recipient domain is not allowed: " + ", ".join(blocked))

    username = env.get("DEFECT_MAIL_USERNAME", "").strip()
    password = None
    if username:
        secret_value = env.get("DEFECT_MAIL_SECRET_FILE", "").strip()
        if not secret_value:
            raise ValueError("DEFECT_MAIL_SECRET_FILE is required with username")
        secret_path = Path(secret_value)
        try:
            mode = stat.S_IMODE(secret_path.stat().st_mode)
            if mode & 0o077:
                raise ValueError("DEFECT_MAIL_SECRET_FILE must not allow group/other access")
            password = secret_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ValueError("DEFECT_MAIL_SECRET_FILE cannot be read") from error
        if not password:
            raise ValueError("DEFECT_MAIL_SECRET_FILE is empty")

    return {
        "host": host,
        "port": port,
        "security": security,
        "sender": sender,
        "recipients": recipients,
        "username": username,
        "password": password,
        "timeout": _positive_setting(env, "DEFECT_MAIL_TIMEOUT_SECONDS", 10),
        "max_attachment_bytes": _positive_setting(
            env, "DEFECT_MAIL_MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024),
        "poll_seconds": _positive_setting(env, "DEFECT_MAIL_POLL_SECONDS", 2),
        "max_attempts": _positive_setting(env, "DEFECT_MAIL_MAX_ATTEMPTS", 10),
        "image_root": Path(env.get("DEFECT_IMAGE_ROOT", str(DEFAULT_IMAGE_ROOT))),
        "max_image_bytes": _positive_setting(
            env, "DEFECT_IMAGE_MAX_BYTES", 10 * 1024 * 1024),
    }


def build_message(report: Path, tokens: dict[str, str],
                  config: dict[str, object]) -> tuple[EmailMessage, str]:
    content = report.read_bytes()
    if len(content) > config["max_attachment_bytes"]:
        raise RuntimeError("report exceeds DEFECT_MAIL_MAX_ATTACHMENT_BYTES")
    sender_domain = str(config["sender"]).rsplit("@", 1)[1]
    message_key = hashlib.sha256(tokens["alert_code"].encode()).hexdigest()[:32]
    message_id = f"<{message_key}@{sender_domain}>"
    message = EmailMessage()
    message["Subject"] = f"[불량대책서] {tokens['part_id']} {tokens['defect_type']}"
    message["From"] = str(config["sender"])
    message["To"] = ", ".join(config["recipients"])
    message["Message-ID"] = message_id
    message["X-Defect-Report-ID"] = tokens["alert_code"]
    message.set_content(
        f"확정 불량 1건이 발생해 대책서를 자동 발행했습니다.\n\n"
        f"문서번호: {tokens['alert_code']}\n"
        f"Job: {tokens['job_id']}\n"
        f"Unit: {tokens['target_unit_id']}\n"
        f"부품/슬롯: {tokens['part_id']} / {tokens['target_slot_code']}\n"
        f"불량 유형: {tokens['defect_type']}\n"
        f"검사 시각: {tokens['target_inspected_at']}\n\n"
        "첨부 문서는 발행 시점의 확정 기록입니다."
    )
    message.add_attachment(
        content,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=report.name,
    )
    return message, message_id


def send_message(message: EmailMessage, config: dict[str, object]) -> None:
    context = ssl.create_default_context()
    arguments = {
        "host": config["host"],
        "port": config["port"],
        "timeout": config["timeout"],
    }
    if config["security"] == "ssl":
        client = smtplib.SMTP_SSL(context=context, **arguments)
    else:
        client = smtplib.SMTP(**arguments)
    with client:
        if config["security"] == "starttls":
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        if config["username"]:
            client.login(config["username"], config["password"])
        refused = client.send_message(message)
        if refused:
            raise RuntimeError("SMTP refused recipients: " + ", ".join(refused))


def claim_delivery(
        dsn: str, unit_defect_id: int | None = None) -> dict[str, object] | None:
    with _connect(dsn) as connection, connection.transaction():
        row = connection.execute(
            """
            WITH candidate AS (
                SELECT unit_defect_id
                FROM production.defect_report_deliveries
                WHERE (
                    (delivery_status = 'PENDING' AND next_attempt_at <= now())
                    OR (delivery_status = 'PROCESSING'
                        AND claimed_at < now() - interval '5 minutes')
                )
                  AND (%s IS NULL OR unit_defect_id = %s)
                ORDER BY next_attempt_at, unit_defect_id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE production.defect_report_deliveries delivery
            SET delivery_status = 'PROCESSING',
                attempt_count = delivery.attempt_count + 1,
                claimed_at = now(),
                last_error = NULL
            FROM candidate
            WHERE delivery.unit_defect_id = candidate.unit_defect_id
            RETURNING delivery.unit_defect_id, delivery.attempt_count
            """,
            (unit_defect_id, unit_defect_id),
        ).fetchone()
        return dict(row) if row else None


def mark_sent(dsn: str, unit_defect_id: int, message_id: str) -> None:
    with _connect(dsn) as connection:
        connection.execute(
            """
            UPDATE production.defect_report_deliveries
            SET delivery_status = 'SENT', sent_at = now(), message_id = %s,
                claimed_at = NULL, last_error = NULL
            WHERE unit_defect_id = %s AND delivery_status = 'PROCESSING'
            """,
            (message_id, unit_defect_id),
        )


def mark_failed(dsn: str, unit_defect_id: int, attempt_count: int,
                max_attempts: int, error: Exception) -> None:
    final = attempt_count >= max_attempts
    delay_seconds = min(300, 2 ** min(attempt_count, 8))
    with _connect(dsn) as connection:
        connection.execute(
            """
            UPDATE production.defect_report_deliveries
            SET delivery_status = %s,
                next_attempt_at = now() + %s * interval '1 second',
                claimed_at = NULL,
                last_error = %s
            WHERE unit_defect_id = %s AND delivery_status = 'PROCESSING'
            """,
            (
                "FAILED" if final else "PENDING",
                delay_seconds,
                str(error)[:1000],
                unit_defect_id,
            ),
        )


def create_report(dsn: str, unit_defect_id: int, path: Path, template: Path,
                  output_dir: Path, image_root: Path,
                  max_image_bytes: int) -> tuple[Path, dict[str, str]]:
    rows = load_defect_context(dsn, unit_defect_id)
    if not rows:
        raise RuntimeError("confirmed defect was not found")
    image = load_inspection_image(
        rows[0]["target_image_path"], image_root, max_image_bytes)
    tokens = build_tokens(rows, path, image)
    output = report_path(output_dir, rows)
    if not output.exists():
        write_report(template, output, tokens, image)
        print(f"created {output}")
    return output, tokens


def process_delivery(dsn: str, delivery: dict[str, object], path: Path,
                     template: Path, output_dir: Path,
                     config: dict[str, object]) -> None:
    unit_defect_id = int(delivery["unit_defect_id"])
    report, tokens = create_report(
        dsn, unit_defect_id, path, template, output_dir,
        config["image_root"], config["max_image_bytes"])
    message, message_id = build_message(report, tokens, config)
    send_message(message, config)
    mark_sent(dsn, unit_defect_id, message_id)
    print(f"sent {tokens['alert_code']}")


def run_worker(dsn: str, path: Path, template: Path, output_dir: Path,
               once: bool = False) -> None:
    config = load_mail_config()
    while True:
        delivery = claim_delivery(dsn)
        if delivery is None:
            if once:
                return
            time.sleep(config["poll_seconds"])
            continue
        try:
            process_delivery(dsn, delivery, path, template, output_dir, config)
        except Exception as error:
            mark_failed(
                dsn,
                int(delivery["unit_defect_id"]),
                int(delivery["attempt_count"]),
                int(config["max_attempts"]),
                error,
            )
            print(f"delivery failed unit_defect_id={delivery['unit_defect_id']}: {error}")
        if once:
            return


def self_check() -> None:
    loaded = datasheet.catalog(DATASHEET)
    assert len(loaded["parts"]["MLCC"]) == 3
    assert loaded["checklist"]["MLCC"]["incoming_inspection"]
    assert re.fullmatch(r"[0-9a-f]{64}", loaded["source_sha256"])
    assert _safe_filename("../CAP") == "CAP"
    tokens = _catalog_tokens("MLCC", "Contoso CX-0603X7R104K100", DATASHEET)
    assert tokens["datasheet_match"] == "일치"
    assert tokens["selected_unit_price"] == "$0.15"
    mock_image = load_inspection_image(
        "InspectionSamples/mock-fail.jpg", DEFAULT_IMAGE_ROOT, 10 * 1024 * 1024)
    assert mock_image["kind"] == "jpeg"
    blocked_image = load_inspection_image(
        "../UI/Icons/item-cap.png", DEFAULT_IMAGE_ROOT, 10 * 1024 * 1024)
    assert blocked_image["status"] == "허용 경로 밖 이미지 차단"
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        secret = directory / "smtp-secret"
        secret.write_text("test-secret", encoding="utf-8")
        secret.chmod(0o600)
        config = load_mail_config({
            "DEFECT_MAIL_HOST": "smtp.example.com",
            "DEFECT_MAIL_FROM": "quality@example.com",
            "DEFECT_MAIL_TO": "owner@example.com",
            "DEFECT_MAIL_ALLOWED_DOMAINS": "example.com",
            "DEFECT_MAIL_USERNAME": "quality@example.com",
            "DEFECT_MAIL_SECRET_FILE": str(secret),
        })
        try:
            load_mail_config({
                "DEFECT_MAIL_HOST": "smtp.example.com",
                "DEFECT_MAIL_FROM": "quality@example.com",
                "DEFECT_MAIL_TO": "outside@invalid.example",
                "DEFECT_MAIL_ALLOWED_DOMAINS": "example.com",
            })
        except ValueError as error:
            assert "not allowed" in str(error)
        else:
            raise AssertionError("recipient allowlist must be enforced")
        try:
            load_mail_config({
                "DEFECT_MAIL_HOST": "smtp.example.com",
                "DEFECT_MAIL_FROM": "quality@example.com",
                "DEFECT_MAIL_TO": "owner@example.com",
                "DEFECT_MAIL_ALLOWED_DOMAINS": "example.com",
                "DEFECT_MAIL_USERNAME": "quality@example.com",
            })
        except ValueError as error:
            assert "SECRET_FILE is required" in str(error)
        else:
            raise AssertionError("authenticated SMTP must require a secret file")
        output = directory / "check.xlsx"
        report_tokens = {"alert_code": "QA-CHECK"}
        report_tokens.update(tokens)
        write_report(TEMPLATE, output, report_tokens, mock_image)
        assert output.is_file()
        message_tokens = {
            "alert_code": "QA-CHECK",
            "part_id": "CAP",
            "defect_type": "CRACK",
            "job_id": "00000000-0000-0000-0000-000000000001",
            "target_unit_id": "1",
            "target_slot_code": "CAP-01",
            "target_inspected_at": "2026-01-01 00:00:00",
        }
        message, message_id = build_message(output, message_tokens, config)
        assert message_id == message["Message-ID"]
        assert next(message.iter_attachments()).get_filename() == output.name
    print("generate_defect_reports self-check passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("MAIN_SERVER_DB_DSN", ""))
    parser.add_argument("--datasheet", type=Path, default=DATASHEET)
    parser.add_argument("--template", type=Path, default=TEMPLATE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--unit-defect-id", type=int)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.dsn.strip():
        parser.error("--dsn or MAIN_SERVER_DB_DSN is required")
    if args.unit_defect_id is not None:
        config = load_mail_config()
        delivery = claim_delivery(args.dsn, args.unit_defect_id)
        if delivery is None:
            parser.error("unit defect delivery is not pending")
        process_delivery(
            args.dsn, delivery, args.datasheet, args.template,
            args.output_dir, config)
        return
    if not args.watch and not args.once:
        parser.error("--unit-defect-id, --watch or --once is required")
    run_worker(
        args.dsn, args.datasheet, args.template, args.output_dir,
        once=args.once)


if __name__ == "__main__":
    main()
