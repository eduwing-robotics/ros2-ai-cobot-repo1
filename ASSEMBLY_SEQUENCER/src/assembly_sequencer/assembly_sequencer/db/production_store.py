"""Transactional PostgreSQL operations owned by the ROS2 assembly process."""

import os
from collections.abc import Mapping
import uuid

import psycopg
from psycopg.rows import dict_row


ACTIVE_JOB_STATUSES = ("PENDING", "RUNNING")
FINAL_JOB_STATUSES = ("COMPLETED", "FAILED", "CANCELLED")
DEFECT_TYPES = {"MISSING", "POSITION_ERROR", "ORIENTATION_ERROR", "CRACK"}


def _connect():
    dsn = os.environ.get("PRODUCTION_DB_DSN")
    if not dsn or not dsn.strip():
        raise RuntimeError("PRODUCTION_DB_DSN is required")
    return psycopg.connect(
        dsn,
        row_factory=dict_row,
    )


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


def record_inspection(unit_id, result, defects, image_path=None):
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
                    """,
                    (unit_id, slot_ids[slot_code], defect_type),
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


def get_product_slot_codes(job_id):
    return [slot["slot_code"] for slot in get_product_slots(job_id)]


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
