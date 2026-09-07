"""Transactional PostgreSQL operations owned by the ROS2 assembly process."""

import os
import copy
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from collections.abc import Mapping
import uuid

import psycopg
from psycopg.rows import dict_row


ACTIVE_JOB_STATUSES = ("PENDING", "RUNNING")
FINAL_JOB_STATUSES = ("COMPLETED", "FAILED", "CANCELLED")
DEFECT_TYPES = {"MISSING", "POSITION_ERROR", "ORIENTATION_ERROR", "CRACK",
                "SEATING_ERROR", "UNCLASSIFIED_ANOMALY"}


def _connect(expected_mode="mock"):
    dsn = os.environ.get("PRODUCTION_DB_DSN", "").strip()
    if not dsn:
        raise RuntimeError("PRODUCTION_DB_DSN is required")
    connection = None
    try:
        connection = psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)
        # Read the administrator-owned database setting, not the session setting:
        # libpq options may override current_setting(), but must not spoof identity.
        row = connection.execute("""
            SELECT split_part(setting, '=', 2) AS runtime_mode
            FROM pg_db_role_setting s
            JOIN pg_database d ON d.oid = s.setdatabase,
                 unnest(s.setconfig) AS setting
            WHERE d.datname = current_database() AND s.setrole = 0
              AND split_part(setting, '=', 1) = 'app.runtime_mode'
        """).fetchone()
        actual = row["runtime_mode"] if row else None
        expected = expected_mode
        if expected not in {"mock", "real"} or actual != expected:
            raise RuntimeError(
                f"MODE_REJECTED stage=db_connect expected={expected!r} actual={actual!r} "
                f"database={connection.info.dbname!r} result=blocked_before_write")
        connection.commit()
        return connection
    except Exception as error:
        if connection is not None:
            connection.close()
        if isinstance(error, RuntimeError):
            raise
        # Preserve the driver's exception category for the existing DB retry policy,
        # but do not forward connection strings in its message.
        if isinstance(error, psycopg.Error):
            raise type(error)("database connection/identity check failed") from None
        raise RuntimeError(f"database connection/identity check failed: {type(error).__name__}") from None


def _positive_id(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")


def _job_id(value, label="job_id"):
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID") from error


def _required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _lock_requirements(cursor, product_id):
    cursor.execute(
        """
        WITH requirements AS (
            SELECT part_id, COUNT(*)::integer AS quantity_per_product
            FROM production.product_slots
            WHERE product_id = %s
            GROUP BY part_id
        )
        SELECT p.part_id, p.stock_quantity, r.quantity_per_product
        FROM production.parts p
        JOIN requirements r ON r.part_id = p.part_id
        ORDER BY p.part_id
        FOR UPDATE OF p
        """,
        (product_id,),
    )
    requirements = cursor.fetchall()
    if not requirements:
        raise RuntimeError("product has no assembly slots")
    return requirements


def _insert_next_unit(cursor, job_id):
    cursor.execute(
        """
        SELECT requested_quantity, job_status
        FROM production.jobs
        WHERE job_id = %s
        FOR UPDATE
        """,
        (job_id,),
    )
    job = cursor.fetchone()
    if job is None:
        raise RuntimeError("job was not found")
    if job["job_status"] != "RUNNING":
        raise RuntimeError("job is not running")

    cursor.execute(
        """
        SELECT COALESCE(MAX(unit_sequence_in_job), 0) AS last_sequence,
               COUNT(*) FILTER (WHERE unit_status = 'RUNNING') AS running_count,
               COUNT(*) FILTER (WHERE inspection_result = 'PASS') AS pass_count
        FROM production.units
        WHERE job_id = %s
        """,
        (job_id,),
    )
    units = cursor.fetchone()
    if units["running_count"]:
        raise RuntimeError("job already has a running unit")
    if units["pass_count"] >= job["requested_quantity"]:
        raise RuntimeError("job already has its requested PASS quantity")

    cursor.execute(
        """
        INSERT INTO production.units (job_id, unit_sequence_in_job)
        VALUES (%s, %s)
        RETURNING unit_id
        """,
        (job_id, units["last_sequence"] + 1),
    )
    return cursor.fetchone()["unit_id"]


def claim_job(job_id, product_code, product_version, recipe_version):
    """Claim a MainServer-created Job and start one Unit attempt."""
    job_id = _job_id(job_id)
    _required_text(product_code, "product_code")
    _required_text(product_version, "product_version")
    _required_text(recipe_version, "recipe_version")

    with _connect() as connection, connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT j.product_id, j.requested_quantity, j.recipe_version,
                       j.job_status, p.product_code, p.product_version,
                       p.is_selectable
                FROM production.jobs j
                JOIN production.products p ON p.product_id = j.product_id
                WHERE j.job_id = %s
                FOR UPDATE OF j, p
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if job is None:
                raise RuntimeError("job was not found")
            if (job["product_code"] != product_code
                    or job["product_version"] != product_version
                    or job["recipe_version"] != recipe_version):
                raise RuntimeError("job product or recipe does not match this Sequencer")
            if not job["is_selectable"]:
                raise RuntimeError("product is not selectable")
            if job["job_status"] not in ACTIVE_JOB_STATUSES:
                raise RuntimeError("job is already finalized")

            if job["job_status"] == "PENDING":
                requirements = _lock_requirements(cursor, job["product_id"])
                shortages = [
                    row["part_id"]
                    for row in requirements
                    if row["stock_quantity"]
                    < row["quantity_per_product"] * job["requested_quantity"]
                ]
                if shortages:
                    raise RuntimeError("insufficient stock: " + ", ".join(shortages))
                cursor.execute(
                    """
                    UPDATE production.products
                    SET definition_locked_at = COALESCE(definition_locked_at, now())
                    WHERE product_id = %s
                    """,
                    (job["product_id"],),
                )
                cursor.execute(
                    """
                    UPDATE production.jobs
                    SET job_status = 'RUNNING', job_started_at = now()
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )

            unit_id = _insert_next_unit(cursor, job_id)
            return {
                "job_id": job_id,
                "unit_id": unit_id,
                "requested_quantity": job["requested_quantity"],
                "recipe_version": job["recipe_version"],
            }


def get_next_runnable_job(product_code, product_version, recipe_version):
    """Return the compatible interrupted or oldest pending Job without claiming it."""
    _required_text(product_code, "product_code")
    _required_text(product_version, "product_version")
    _required_text(recipe_version, "recipe_version")
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT j.job_id::text AS job_id
            FROM production.jobs j
            JOIN production.products p ON p.product_id = j.product_id
            WHERE (
                    j.job_status = 'RUNNING'
                    AND NOT EXISTS (
                        SELECT 1 FROM production.units u
                        WHERE u.job_id = j.job_id
                          AND u.unit_status = 'RUNNING'
                    )
                  OR j.job_status = 'PENDING'
                    AND NOT EXISTS (
                        SELECT 1 FROM production.jobs active
                        WHERE active.job_status = 'RUNNING'
                    )
              )
              AND j.recipe_version = %s
              AND p.product_code = %s
              AND p.product_version = %s
              AND p.is_selectable
            ORDER BY (j.job_status = 'RUNNING') DESC, j.requested_at, j.job_id
            LIMIT 1
            """,
            (recipe_version, product_code, product_version),
        )
        return cursor.fetchone()


def recover_interrupted_units():
    """Fail interrupted Unit attempts while leaving their Jobs resumable."""
    with _connect() as connection, connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE production.units u
                SET unit_status = 'FAILED'
                FROM production.jobs j
                WHERE u.job_id = j.job_id
                  AND u.unit_status = 'RUNNING'
                  AND j.job_status = 'RUNNING'
                RETURNING u.unit_id
                """
            )
            return len(cursor.fetchall())


def complete_assembly_and_consume_stock(unit_id):
    _positive_id(unit_id, "unit_id")

    with _connect() as connection, connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.unit_status, u.assembly_completed_at,
                       j.job_status, j.product_id
                FROM production.units u
                JOIN production.jobs j ON j.job_id = u.job_id
                WHERE u.unit_id = %s
                FOR UPDATE OF u, j
                """,
                (unit_id,),
            )
            unit = cursor.fetchone()
            if unit is None:
                raise RuntimeError("unit was not found")
            if unit["assembly_completed_at"] is not None:
                return
            if unit["unit_status"] != "RUNNING" or unit["job_status"] != "RUNNING":
                raise RuntimeError("unit and job must be running")

            requirements = _lock_requirements(cursor, unit["product_id"])
            shortages = [
                row["part_id"]
                for row in requirements
                if row["stock_quantity"] < row["quantity_per_product"]
            ]
            if shortages:
                raise RuntimeError("insufficient stock: " + ", ".join(shortages))

            cursor.execute(
                """
                WITH requirements AS (
                    SELECT part_id, COUNT(*)::integer AS quantity_per_product
                    FROM production.product_slots
                    WHERE product_id = %s
                    GROUP BY part_id
                ), changed AS (
                    UPDATE production.parts p
                    SET stock_quantity = p.stock_quantity - r.quantity_per_product
                    FROM requirements r
                    WHERE p.part_id = r.part_id
                    RETURNING p.part_id
                )
                INSERT INTO production.inventory_movements (
                    part_id, quantity_delta, movement_type, unit_id, reason
                )
                SELECT changed.part_id, -requirements.quantity_per_product,
                       'CONSUMPTION', %s, 'ASSEMBLY_COMPLETED'
                FROM changed
                JOIN requirements USING (part_id)
                """,
                (unit["product_id"], unit_id),
            )
            cursor.execute(
                """
                UPDATE production.units
                SET assembly_completed_at = now()
                WHERE unit_id = %s
                """,
                (unit_id,),
            )


def normalize_defects(result, defects):
    if result not in ("PASS", "FAIL"):
        raise ValueError("result must be PASS or FAIL")
    try:
        defects = list(defects)
    except TypeError as error:
        raise ValueError("defects must be an iterable of mappings") from error
    if result == "PASS" and defects:
        raise ValueError("PASS must not contain defects")
    if result == "FAIL" and not defects:
        raise ValueError("FAIL must contain at least one defect")

    normalized = []
    seen_slots = set()
    for defect in defects:
        if not isinstance(defect, Mapping) or set(defect) != {"slot_code", "defect_type"}:
            raise ValueError("each defect requires slot_code and defect_type")
        slot_code = defect["slot_code"]
        defect_type = defect["defect_type"]
        _required_text(slot_code, "slot_code")
        if defect_type not in DEFECT_TYPES:
            raise ValueError("unsupported defect_type")
        if slot_code in seen_slots:
            raise ValueError("a slot can contain only one defect")
        seen_slots.add(slot_code)
        normalized.append((slot_code, defect_type))
    return sorted(normalized)


def record_inspection(unit_id, result, defects, image_path=None, *, inspection=None, image_bytes=None):
    """Record a final inspection; Vision data also persists immutable files and slot UID links.

    Vision callers pass the backend's data/image_bytes with result and defects=None.
    UNKNOWN holds the Unit RUNNING. Reinspection and different-content retries are rejected.
    """
    if inspection is not None:
        if defects is not None or image_path is not None or result != inspection.get("result", {}).get("decision"):
            raise ValueError("Vision result must be passed without separate defects or image_path")
        return _record_vision_inspection(unit_id, inspection, image_bytes)
    _positive_id(unit_id, "unit_id")
    if image_path is not None and not isinstance(image_path, str):
        raise ValueError("image_path must be a string or None")
    normalized = normalize_defects(result, defects)

    with _connect() as connection, connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.unit_status, u.inspection_result,
                       u.inspection_image_path, u.assembly_completed_at,
                       j.product_id, j.job_status
                FROM production.units u
                JOIN production.jobs j ON j.job_id = u.job_id
                WHERE u.unit_id = %s
                FOR UPDATE OF u, j
                """,
                (unit_id,),
            )
            unit = cursor.fetchone()
            if unit is None:
                raise RuntimeError("unit was not found")
            if unit["inspection_result"] != "PENDING":
                cursor.execute(
                    """
                    SELECT ps.slot_code, ud.defect_type
                    FROM production.unit_defects ud
                    JOIN production.product_slots ps
                      ON ps.product_slot_id = ud.product_slot_id
                    WHERE ud.unit_id = %s
                    ORDER BY ps.slot_code
                    """,
                    (unit_id,),
                )
                existing = sorted(
                    (row["slot_code"], row["defect_type"])
                    for row in cursor.fetchall()
                )
                if (unit["inspection_result"] == result
                        and unit["inspection_image_path"] == image_path
                        and existing == normalized):
                    return
                raise RuntimeError("inspection is already finalized with different data")
            if unit["job_status"] != "RUNNING":
                raise RuntimeError("job is not running")
            if unit["unit_status"] != "RUNNING":
                raise RuntimeError("unit is not running")
            if unit["assembly_completed_at"] is None:
                raise RuntimeError("assembly is not completed")

            slot_ids = {}
            if normalized:
                cursor.execute(
                    """
                    SELECT product_slot_id, slot_code
                    FROM production.product_slots
                    WHERE product_id = %s AND slot_code = ANY(%s)
                    """,
                    (unit["product_id"], [slot for slot, _ in normalized]),
                )
                slot_ids = {
                    row["slot_code"]: row["product_slot_id"]
                    for row in cursor.fetchall()
                }
                if len(slot_ids) != len(normalized):
                    raise RuntimeError("defect slot does not belong to the unit product")

            for slot_code, defect_type in normalized:
                cursor.execute(
                    """
                    INSERT INTO production.unit_defects (
                        unit_id, product_slot_id, defect_type
                    )
                    VALUES (%s, %s, %s)
                    RETURNING unit_defect_id
                    """,
                    (unit_id, slot_ids[slot_code], defect_type),
                )
                unit_defect_id = cursor.fetchone()["unit_defect_id"]
                cursor.execute(
                    """
                    INSERT INTO production.defect_report_deliveries (unit_defect_id)
                    VALUES (%s)
                    """,
                    (unit_defect_id,),
                )
            cursor.execute(
                """
                UPDATE production.units
                SET unit_status = %s,
                    inspection_result = %s,
                    inspection_image_path = %s,
                    inspected_at = now()
                WHERE unit_id = %s
                """,
                ("COMPLETED", result, image_path, unit_id),
            )


def _record_vision_inspection(unit_id, inspection, image_bytes):
    _positive_id(unit_id, "unit_id")
    data = copy.deepcopy(inspection)
    if (data.get("unit_id") != unit_id or type(data.get("unit_id")) is not int
            or data.get("status") != "COMPLETED"):
        raise ValueError("Vision must return COMPLETED for the requested Unit")
    job_id = _job_id(data.get("job_id"))
    _job_id(data.get("inspection_id"), "inspection_id")
    result = data.get("result", {})
    decision = result.get("decision")
    if decision not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ValueError("Vision decision must be PASS, FAIL or UNKNOWN")
    inspected_at = datetime.fromisoformat(result["inspected_at"])
    if inspected_at.tzinfo is None:
        raise ValueError("Vision inspected_at must include a timezone")
    slots, findings, defects = (result.get(k) for k in ("slots", "findings", "defects"))
    if not all(isinstance(items, list) for items in (slots, findings, defects)):
        raise ValueError("Vision slots, findings and defects must be arrays")
    slot_map = {}
    for slot in slots:
        code = slot.get("slot_code")
        _required_text(code, "slot_code")
        if code in slot_map or slot.get("decision") not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ValueError("duplicate slot or invalid slot decision")
        slot_map[code] = slot
    for finding in findings:
        if (finding.get("slot_code") not in slot_map
                or type(finding.get("confirmed_defect")) is not bool):
            raise ValueError("finding must identify a known slot and confirmation flag")
    # Preserve the raw codes in JSON; only established synonyms are normalized for SQL.
    aliases = {"COMPONENT_MISSING": "MISSING", "DIRECTION_ERROR": "ORIENTATION_ERROR"}
    confirmed = {}
    for defect in defects:
        code = defect.get("slot_code")
        candidates = [f for f in findings if f["slot_code"] == code and f["confirmed_defect"]]
        if (code not in slot_map or not candidates
                or any(f.get("authority") in (None, "ADVISORY", "ADVISORY_ONLY", "DISABLED") for f in candidates)):
            raise ValueError("defect lacks a confirmed authoritative finding")
        kinds = {aliases.get(f.get("primary_defect_code"), f.get("primary_defect_code")) for f in candidates}
        if len(kinds) != 1 or not kinds.issubset(DEFECT_TYPES) or code in confirmed:
            raise ValueError("unsupported or multiple confirmed defect types in one slot")
        confirmed[code] = kinds.pop()
    if {f["slot_code"] for f in findings if f["confirmed_defect"]} != set(confirmed):
        raise ValueError("confirmed findings and defects disagree")
    if (decision == "FAIL") != bool(confirmed):
        raise ValueError("only a confirmed FAIL may contain production defects")
    if decision == "PASS" and any(slot["decision"] != "PASS" for slot in slots):
        raise ValueError("PASS requires all slots to pass")
    image = data.get("image", {})
    if type(image.get("ready")) is not bool:
        raise ValueError("Vision image.ready must be boolean")
    if image["ready"]:
        if (not isinstance(image_bytes, bytes) or not image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
                or len(image_bytes) != image.get("size_bytes")
                or hashlib.sha256(image_bytes).hexdigest() != image.get("sha256")):
            raise ValueError("Vision PNG size or SHA256 mismatch")
    elif image_bytes is not None:
        raise ValueError("unexpected PNG for an unready image")
    root_value = os.environ.get("DEFECT_IMAGE_ROOT", "").strip()
    if not root_value:
        raise ValueError("DEFECT_IMAGE_ROOT must identify the shared inspection storage")
    root = Path(root_value).resolve(strict=True)
    relative = Path("inspections") / str(unit_id)
    folder = (root / relative).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("inspection storage is outside the shared root")
    image_path = (relative / "02_annotated_report.png").as_posix() if image["ready"] else None

    def write_file(path, content):
        if path.exists() and path.read_bytes() == content:
            return
        # Replace only the derived UID map; the source response is checked before writing.
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temporary:
            temporary_name = temporary.name
            try:
                temporary.write(content)
                temporary.flush()
                os.fchmod(temporary.fileno(), 0o640)
                os.fsync(temporary.fileno())
            except BaseException:
                os.unlink(temporary_name)
                raise
        try:
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    with _connect(expected_mode="real") as connection, connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.unit_status, u.inspection_result, u.inspected_at,
                       u.inspection_image_path, u.assembly_completed_at,
                       j.job_id::text AS job_id, j.product_id, j.job_status
                FROM production.units u JOIN production.jobs j USING (job_id)
                WHERE u.unit_id = %s FOR UPDATE OF u, j
            """, (unit_id,))
            unit = cursor.fetchone()
            if unit is None or unit["job_id"] != job_id:
                raise ValueError("Vision Job/Unit does not match production")
            cursor.execute("""
                SELECT product_slot_id, slot_code, part_id FROM production.product_slots
                WHERE product_id = %s ORDER BY slot_code
            """, (unit["product_id"],))
            product_slots = cursor.fetchall()
            if (not product_slots or {r["slot_code"] for r in product_slots} != set(slot_map)
                    or any(slot_map[r["slot_code"]].get("part_id") != r["part_id"] for r in product_slots)):
                raise ValueError("Vision slots/parts must exactly match the product")
            source = folder / "response.json"
            prior = json.loads(source.read_bytes()) if source.exists() else None
            if prior is not None and prior != {"data": data}:
                raise RuntimeError("Unit already has different Vision data; reinspection is disabled")
            replay = unit["inspection_result"] != "PENDING"
            if replay:
                if (prior is None or unit["inspection_result"] != decision
                        or unit["inspection_image_path"] != image_path or unit["inspected_at"] != inspected_at):
                    raise RuntimeError("inspection is already finalized with different data")
            elif (unit["job_status"] != "RUNNING" or unit["unit_status"] != "RUNNING"
                    or unit["assembly_completed_at"] is None):
                raise RuntimeError("Job/Unit must be running with completed assembly")
            folder.mkdir(parents=True, exist_ok=True)
            write_file(source, json.dumps({"data": data}, ensure_ascii=False, sort_keys=True).encode())
            if image["ready"]:
                write_file(folder / "02_annotated_report.png", image_bytes)
            links = []
            for slot in product_slots:
                kind = confirmed.get(slot["slot_code"])
                if not replay:
                    cursor.execute("""
                        INSERT INTO production.unit_defects (unit_id, product_slot_id, defect_type)
                        VALUES (%s, %s, %s)
                    """, (unit_id, slot["product_slot_id"], kind))
                cursor.execute("""
                    SELECT unit_defect_id, defect_type FROM production.unit_defects
                    WHERE unit_id = %s AND product_slot_id = %s
                """, (unit_id, slot["product_slot_id"]))
                row = cursor.fetchone()
                if row is None or row["defect_type"] != kind:
                    raise RuntimeError("stored slot result does not match Vision")
                links.append({"slot_code": slot["slot_code"], "unit_defect_id": row["unit_defect_id"]})
                # No image means no immutable report yet; UNKNOWN never creates a delivery.
                if kind is not None and image["ready"]:
                    cursor.execute("""
                        INSERT INTO production.defect_report_deliveries (unit_defect_id)
                        VALUES (%s) ON CONFLICT (unit_defect_id) DO NOTHING
                    """, (row["unit_defect_id"],))
            # Files precede commit. Readers verify these UID links against committed rows;
            # a rollback leaves recoverable files, never a visible fabricated inspection.
            write_file(folder / "result.json", json.dumps(
                {"data": data, "unit_defects": links}, ensure_ascii=False, sort_keys=True).encode())
            # Persist directory entries before committing DB references to these files.
            for directory in (folder, folder.parent, root):
                descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            if not replay:
                cursor.execute("""
                    UPDATE production.units SET unit_status = %s, inspection_result = %s,
                        inspection_image_path = %s, inspected_at = %s WHERE unit_id = %s
                """, ("RUNNING" if decision == "UNKNOWN" else "COMPLETED",
                      decision, image_path, inspected_at, unit_id))
    return links


def finish_job(job_id, final_status):
    job_id = _job_id(job_id)
    if final_status not in FINAL_JOB_STATUSES:
        raise ValueError("final_status must be COMPLETED, FAILED or CANCELLED")

    with _connect() as connection, connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT requested_quantity, job_status
                FROM production.jobs
                WHERE job_id = %s
                FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if job is None:
                raise RuntimeError("job was not found")
            if job["job_status"] == final_status:
                return
            if job["job_status"] in FINAL_JOB_STATUSES:
                raise RuntimeError("job is already finalized with a different status")

            cursor.execute(
                """
                SELECT COUNT(*) FILTER (
                           WHERE inspection_result = 'PASS'
                       ) AS pass_count,
                       COUNT(*) FILTER (
                           WHERE unit_status = 'RUNNING'
                       ) AS running_count
                FROM production.units
                WHERE job_id = %s
                """,
                (job_id,),
            )
            units = cursor.fetchone()
            if final_status == "COMPLETED":
                if (units["pass_count"] < job["requested_quantity"]
                        or units["running_count"] != 0):
                    raise RuntimeError("job has not reached its requested PASS quantity")
            else:
                cursor.execute(
                    """
                    UPDATE production.units
                    SET unit_status = 'FAILED'
                    WHERE job_id = %s AND unit_status = 'RUNNING'
                    """,
                    (job_id,),
                )

            cursor.execute(
                """
                UPDATE production.jobs
                SET job_status = %s, job_finished_at = now()
                WHERE job_id = %s
                """,
                (final_status, job_id),
            )


def _get_job_state(connection, job_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT job_id, product_id, requested_quantity, recipe_version,
                   job_status, requested_at, job_started_at, job_finished_at
            FROM production.jobs
            WHERE job_id = %s
            """,
            (job_id,),
        )
        state = cursor.fetchone()
        if state is None:
            raise RuntimeError("job was not found")
        state = dict(state)
        state["job_id"] = str(state["job_id"])
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (
                       WHERE inspection_result = 'PASS'
                   ) AS completed_quantity,
                   COUNT(*) FILTER (
                       WHERE unit_status = 'FAILED'
                   ) AS failed_quantity,
                   COUNT(*) FILTER (
                       WHERE unit_status = 'RUNNING'
                   ) AS running_quantity,
                   MAX(unit_id) FILTER (
                       WHERE unit_status = 'RUNNING'
                   ) AS current_unit_id
            FROM production.units
            WHERE job_id = %s
            """,
            (job_id,),
        )
        state.update(cursor.fetchone())
        return state


def get_job_state(job_id):
    job_id = _job_id(job_id)
    with _connect() as connection:
        return _get_job_state(connection, job_id)


def get_product_slots(job_id):
    job_id = _job_id(job_id)
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ps.slot_code, ps.part_id
                FROM production.jobs j
                JOIN production.product_slots ps ON ps.product_id = j.product_id
                WHERE j.job_id = %s
                ORDER BY ps.slot_code
                """,
                (job_id,),
            )
            slots = [dict(row) for row in cursor.fetchall()]
            if not slots:
                raise RuntimeError("job or product slots were not found")
            return slots
