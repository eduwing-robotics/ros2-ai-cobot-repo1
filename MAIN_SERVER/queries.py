"""Production reads and durable Job creation used by MainServer."""
import os
import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


class ResourceNotFound(LookupError):
    pass


class DuplicateRequest(RuntimeError):
    pass


class JobNotCancellable(RuntimeError):
    pass


def _connect():
    dsn = os.environ.get("MAIN_SERVER_DB_DSN", "").strip()
    if not dsn:
        raise DatabaseUnavailable("MAIN_SERVER_DB_DSN is required")
    try:
        return psycopg.connect(dsn, row_factory=dict_row)
    except psycopg.Error as error:
        raise DatabaseUnavailable("database connection failed") from error


def _all(sql, values=()):
    try:
        with _connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, values)
            return cursor.fetchall()
    except DatabaseUnavailable:
        raise
    except psycopg.Error as error:
        raise DatabaseUnavailable("database query failed") from error


def _one(sql, values=()):
    rows = _all(sql, values)
    return rows[0] if rows else None


def health():
    return _one("SELECT current_database() AS database_name, now() AS database_time")


def create_job(command):
    """Create one idempotent production Job without storing robot payload."""
    try:
        with _connect() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO production.jobs (
                        job_id, product_id, requested_quantity, recipe_version
                    )
                    SELECT %s, product_id, %s, %s
                    FROM production.products
                    WHERE product_code = %s
                      AND product_version = %s
                      AND is_selectable
                    ON CONFLICT (job_id) DO NOTHING
                    RETURNING job_status
                    """,
                    (
                        command["job_id"], command["requested_quantity"],
                        command["recipe_version"], command["product_code"],
                        command["product_version"],
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is not None:
                    status = inserted["job_status"]
                else:
                    cursor.execute(
                        """
                        SELECT j.job_status, j.requested_quantity,
                               j.recipe_version, p.product_code,
                               p.product_version
                        FROM production.jobs j
                        JOIN production.products p ON p.product_id = j.product_id
                        WHERE j.job_id = %s
                        """,
                        (command["job_id"],),
                    )
                    existing = cursor.fetchone()
                    if existing is None:
                        raise ResourceNotFound("selectable product was not found")
                    expected = {
                        "requested_quantity": command["requested_quantity"],
                        "recipe_version": command["recipe_version"],
                        "product_code": command["product_code"],
                        "product_version": command["product_version"],
                    }
                    if any(existing[field] != value
                           for field, value in expected.items()):
                        raise DuplicateRequest(
                            "job_id is already used by a different request"
                        )
                    status = existing["job_status"]
        return {
            "accepted": True,
            "job_id": command["job_id"],
            "status": status,
        }
    except (DatabaseUnavailable, DuplicateRequest):
        raise
    except psycopg.Error as error:
        raise DatabaseUnavailable("database query failed") from error


def cancel_pending_job(job_id):
    """Cancel only a durable Job that the Sequencer has not claimed."""
    try:
        with _connect() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT job_status FROM production.jobs
                    WHERE job_id = %s FOR UPDATE
                    """,
                    (job_id,),
                )
                job = cursor.fetchone()
                if job is None:
                    raise ResourceNotFound("job was not found")
                if job["job_status"] != "PENDING":
                    raise JobNotCancellable("only PENDING jobs can be cancelled")
                cursor.execute(
                    """
                    UPDATE production.jobs
                    SET job_status = 'CANCELLED', job_finished_at = now()
                    WHERE job_id = %s
                    RETURNING job_id, job_status
                    """,
                    (job_id,),
                )
                return dict(cursor.fetchone())
    except (DatabaseUnavailable, ResourceNotFound, JobNotCancellable):
        raise
    except psycopg.Error as error:
        raise DatabaseUnavailable("database query failed") from error


def products():
    return _all("""
        WITH required_parts AS (
            SELECT product_id, part_id, COUNT(*) AS quantity_per_product
            FROM production.product_slots GROUP BY product_id, part_id
        )
        SELECT pr.product_id, pr.product_code, pr.product_name, pr.product_version,
               pr.is_selectable,
               COALESCE(MIN(FLOOR(p.stock_quantity::numeric / rp.quantity_per_product)), 0)
                   ::bigint AS buildable_quantity
        FROM production.products pr
        LEFT JOIN required_parts rp ON rp.product_id = pr.product_id
        LEFT JOIN production.parts p ON p.part_id = rp.part_id
        WHERE pr.is_selectable
        GROUP BY pr.product_id, pr.product_code, pr.product_name, pr.product_version,
                 pr.is_selectable
        ORDER BY pr.product_code, pr.product_version
    """)


def product(product_id):
    row = _one("""
        SELECT product_id, product_code, product_name, product_version, is_selectable
        FROM production.products WHERE product_id = %s
    """, (product_id,))
    if row is None:
        raise ResourceNotFound("product was not found")
    row["slots"] = _all("""
        SELECT ps.product_slot_id, ps.slot_code, p.part_id, p.part_name,
               p.part_category, p.stock_quantity
        FROM production.product_slots ps JOIN production.parts p ON p.part_id = ps.part_id
        WHERE ps.product_id = %s ORDER BY ps.slot_code
    """, (product_id,))
    return row


def requirements(product_id, quantity):
    if _one("SELECT 1 FROM production.products WHERE product_id = %s", (product_id,)) is None:
        raise ResourceNotFound("product was not found")
    return _all("""
        SELECT p.part_id, p.part_name, p.part_category,
               COUNT(*)::integer AS quantity_per_product,
               (COUNT(*) * %s)::integer AS required_quantity, p.stock_quantity,
               GREATEST(COUNT(*) * %s - p.stock_quantity, 0)::integer AS shortage_quantity
        FROM production.product_slots ps JOIN production.parts p ON p.part_id = ps.part_id
        WHERE ps.product_id = %s
        GROUP BY p.part_id, p.part_name, p.part_category, p.stock_quantity
        ORDER BY p.part_id
    """, (quantity, quantity, product_id))


def part(part_id):
    row = _one("""
        SELECT part_id, part_name, part_category, stock_quantity
        FROM production.parts WHERE part_id = %s
    """, (part_id,))
    if row is None:
        raise ResourceNotFound("part was not found")
    return row


def job(job_id):
    row = _one("""
        SELECT j.job_id, j.product_id, pr.product_code, pr.product_version,
               j.recipe_version, j.job_status, j.requested_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.inspection_result = 'PASS')::integer AS completed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'RUNNING')::integer AS running_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'FAILED')::integer AS failed_quantity,
               ROUND(100.0 * COUNT(u.unit_id) FILTER (WHERE u.inspection_result = 'PASS')
                     / j.requested_quantity, 2) AS progress_percent,
               j.requested_at, j.job_started_at, j.job_finished_at
        FROM production.jobs j JOIN production.products pr ON pr.product_id = j.product_id
        LEFT JOIN production.units u ON u.job_id = j.job_id
        WHERE j.job_id = %s
        GROUP BY j.job_id, j.product_id, pr.product_code, pr.product_version,
                 j.recipe_version, j.job_status, j.requested_quantity,
                 j.requested_at, j.job_started_at, j.job_finished_at
    """, (job_id,))
    if row is None:
        raise ResourceNotFound("job was not found")
    return row


def jobs(status=None, limit=12):
    """List the active queue first, followed by recent production Jobs."""
    return _all("""
        SELECT j.job_id, j.product_id, pr.product_code, pr.product_name,
               pr.product_version, j.recipe_version, j.job_status,
               j.requested_quantity,
               COUNT(u.unit_id)::integer AS attempted_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.inspection_result = 'PASS')::integer AS completed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'RUNNING')::integer AS running_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'FAILED')::integer AS failed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.inspection_result = 'FAIL')::integer AS inspection_failed_quantity,
               ROUND(100.0 * COUNT(u.unit_id) FILTER (WHERE u.inspection_result = 'PASS')
                     / j.requested_quantity, 2) AS progress_percent,
               j.requested_at, j.job_started_at, j.job_finished_at
        FROM production.jobs j
        JOIN production.products pr ON pr.product_id = j.product_id
        LEFT JOIN production.units u ON u.job_id = j.job_id
        WHERE (%s::text IS NULL OR j.job_status::text = %s)
        GROUP BY j.job_id, j.product_id, pr.product_code, pr.product_name,
                 pr.product_version, j.recipe_version, j.job_status,
                 j.requested_quantity, j.requested_at, j.job_started_at,
                 j.job_finished_at
        ORDER BY CASE j.job_status
                     WHEN 'RUNNING' THEN 0
                     WHEN 'PENDING' THEN 1
                     ELSE 2
                 END,
                 j.requested_at DESC, j.job_id
        LIMIT %s
    """, (status, status, limit))


def units(job_id):
    if _one("SELECT 1 FROM production.jobs WHERE job_id = %s", (job_id,)) is None:
        raise ResourceNotFound("job was not found")
    rows = _all("""
        SELECT unit_id, unit_sequence_in_job, unit_status, inspection_result,
               inspection_image_path, assembly_started_at, assembly_completed_at, inspected_at
        FROM production.units WHERE job_id = %s ORDER BY unit_sequence_in_job
    """, (job_id,))
    defects = _all("""
        SELECT ud.unit_id, ps.slot_code, ud.defect_type
        FROM production.unit_defects ud
        JOIN production.product_slots ps ON ps.product_slot_id = ud.product_slot_id
        JOIN production.units u ON u.unit_id = ud.unit_id
        WHERE u.job_id = %s ORDER BY ud.unit_id, ps.slot_code
    """, (job_id,))
    by_unit = {}
    for defect in defects:
        by_unit.setdefault(defect.pop("unit_id"), []).append(defect)
    for row in rows:
        row["defects"] = by_unit.get(row["unit_id"], [])
    return rows


def slot_rates(product_id):
    if _one("SELECT 1 FROM production.products WHERE product_id = %s", (product_id,)) is None:
        raise ResourceNotFound("product was not found")
    return _all("""
        SELECT ps.product_slot_id, ps.slot_code, p.part_id, p.part_name,
               COUNT(u.unit_id)::integer AS inspected_quantity,
               COUNT(ud.unit_defect_id)::integer AS defective_quantity,
               ROUND(100.0 * COUNT(ud.unit_defect_id) / NULLIF(COUNT(u.unit_id), 0), 2)
                   AS defect_rate_percent
        FROM production.product_slots ps JOIN production.parts p ON p.part_id = ps.part_id
        LEFT JOIN production.jobs j ON j.product_id = ps.product_id
        LEFT JOIN production.units u ON u.job_id = j.job_id
                              AND u.inspection_result IN ('PASS', 'FAIL')
        LEFT JOIN production.unit_defects ud ON ud.unit_id = u.unit_id
                                             AND ud.product_slot_id = ps.product_slot_id
        WHERE ps.product_id = %s
        GROUP BY ps.product_slot_id, ps.slot_code, p.part_id, p.part_name
        ORDER BY ps.slot_code
    """, (product_id,))
