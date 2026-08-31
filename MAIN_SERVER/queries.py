"""Production reads and durable command enqueue used by MainServer."""
import os
import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


class ResourceNotFound(LookupError):
    pass


class DuplicateRequest(RuntimeError):
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


def enqueue_assembly(command, mode):
    """Persist one command without interpreting robot or production state."""
    try:
        with _connect() as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO control.assembly_requests (
                        request_id, runtime_mode, payload
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (request_id) DO NOTHING
                    RETURNING request_status
                    """,
                    (command["request_id"], mode, psycopg.types.json.Jsonb(command)),
                )
                inserted = cursor.fetchone()
                if inserted is not None:
                    status = inserted["request_status"]
                else:
                    cursor.execute(
                        """
                        SELECT runtime_mode, payload, request_status
                        FROM control.assembly_requests
                        WHERE request_id = %s
                        """,
                        (command["request_id"],),
                    )
                    existing = cursor.fetchone()
                    if (existing is None or existing["runtime_mode"] != mode
                            or existing["payload"] != command):
                        raise DuplicateRequest(
                            "request_id is already used by a different command"
                        )
                    status = existing["request_status"]
        return {
            "accepted": True,
            "request_id": command["request_id"],
            "status": status,
        }
    except (DatabaseUnavailable, DuplicateRequest):
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
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'COMPLETED')::integer AS completed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'RUNNING')::integer AS running_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'FAILED')::integer AS failed_quantity,
               ROUND(100.0 * COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'COMPLETED')
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
