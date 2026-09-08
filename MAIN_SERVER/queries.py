"""Production reads and durable Job creation used by MainServer."""
import os
import json
import hashlib
from pathlib import Path
import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


class InspectionUnavailable(RuntimeError):
    pass


class ResourceNotFound(LookupError):
    pass


class DuplicateRequest(RuntimeError):
    pass


class JobNotCancellable(RuntimeError):
    pass


def _connect(dsn=None):
    dsn = (os.environ.get("MAIN_SERVER_DB_DSN", "") if dsn is None else dsn).strip()
    if not dsn:
        raise DatabaseUnavailable("MAIN_SERVER_DB_DSN is required")
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
        expected = os.environ.get("MAIN_SERVER_MODE")
        if expected not in {"mock", "real"} or actual != expected:
            raise DatabaseUnavailable(
                f"MODE_REJECTED stage=db_connect expected={expected!r} actual={actual!r} "
                f"database={connection.info.dbname!r} result=blocked_before_write")
        connection.commit()
        return connection
    except Exception as error:
        if connection is not None:
            connection.close()
        if isinstance(error, DatabaseUnavailable):
            raise
        # Driver text may contain connection credentials; retain only its type.
        raise DatabaseUnavailable(f"database connection/identity check failed: {type(error).__name__}") from None


def _all(sql, values=(), dsn=None):
    try:
        with _connect(dsn) as connection, connection.cursor() as cursor:
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
               COUNT(u.unit_id) FILTER (
                   WHERE u.unit_status = 'COMPLETED' AND u.inspection_result = 'PASS'
               )::integer AS completed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'RUNNING')::integer AS running_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'FAILED')::integer AS failed_quantity,
               ROUND(100.0 * COUNT(u.unit_id) FILTER (
                         WHERE u.unit_status = 'COMPLETED' AND u.inspection_result = 'PASS')
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
        WITH selected_jobs AS (
            SELECT * FROM production.jobs
            WHERE (%s::text IS NULL OR job_status::text = %s)
            ORDER BY CASE job_status
                         WHEN 'RUNNING' THEN 0
                         WHEN 'PENDING' THEN 1
                         ELSE 2
                     END,
                     requested_at DESC, job_id
            LIMIT %s
        )
        SELECT j.job_id, j.product_id, pr.product_code, pr.product_name,
               pr.product_version, j.recipe_version, j.job_status,
               j.requested_quantity,
               COUNT(u.unit_id)::integer AS attempted_quantity,
               COUNT(u.unit_id) FILTER (
                   WHERE u.unit_status = 'COMPLETED' AND u.inspection_result = 'PASS'
               )::integer AS completed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'RUNNING')::integer AS running_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.unit_status = 'FAILED')::integer AS failed_quantity,
               COUNT(u.unit_id) FILTER (WHERE u.inspection_result = 'FAIL')::integer AS inspection_failed_quantity,
               ROUND(100.0 * COUNT(u.unit_id) FILTER (
                         WHERE u.unit_status = 'COMPLETED' AND u.inspection_result = 'PASS')
                     / j.requested_quantity, 2) AS progress_percent,
               j.requested_at, j.job_started_at, j.job_finished_at
        FROM selected_jobs j
        JOIN production.products pr ON pr.product_id = j.product_id
        LEFT JOIN production.units u ON u.job_id = j.job_id
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
        SELECT ud.unit_id, ud.unit_defect_id, ps.slot_code, ud.defect_type
        FROM production.unit_defects ud
        JOIN production.product_slots ps ON ps.product_slot_id = ud.product_slot_id
        JOIN production.units u ON u.unit_id = ud.unit_id
        WHERE u.job_id = %s ORDER BY ud.unit_id, ps.slot_code
    """, (job_id,))
    by_unit = {}
    for defect in defects:
        by_unit.setdefault(defect.pop("unit_id"), []).append(defect)
    for row in rows:
        slot_rows = by_unit.get(row["unit_id"], [])
        row["defects"] = [item for item in slot_rows if item["defect_type"] is not None]
        row["inspection"] = None
        row["inspection_error"] = None
        try:
            row["inspection"] = _load_inspection(row, job_id, slot_rows)
        except InspectionUnavailable as error:
            row["inspection_error"] = str(error)
        row["inspection_image_url"] = (
            f"/api/v1/units/{row['unit_id']}/inspection/image"
            if row["inspection"] and row["inspection"]["image"]["ready"] else None
        )
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
                                             AND ud.defect_type IS NOT NULL
        WHERE ps.product_id = %s
        GROUP BY ps.product_slot_id, ps.slot_code, p.part_id, p.part_name
        ORDER BY ps.slot_code
    """, (product_id,))


def _inspection_root(root=None):
    return Path(root if root is not None else os.environ.get(
        "DEFECT_IMAGE_ROOT", str(Path(__file__).resolve().parent.parent / "UnityDT/Assets/StreamingAssets")
    )).resolve()


def _load_inspection(unit, job_id, slot_rows, root=None):
    if unit["inspection_result"] == "PENDING":
        return None
    root = _inspection_root(root)
    path = (root / "inspections" / str(unit["unit_id"]) / "result.json").resolve()
    if not path.is_relative_to(root):
        raise InspectionUnavailable("inspection path is outside storage")
    if not path.exists():
        if any(row["defect_type"] is None for row in slot_rows) or unit["inspection_result"] == "UNKNOWN":
            raise InspectionUnavailable("inspection JSON is not available")
        return None  # Legacy PASS/FAIL records have no Vision JSON.
    try:
        with path.open("rb") as source:
            raw = source.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("inspection JSON exceeds 4 MiB")
        stored = json.loads(raw)
        data = stored["data"]
        if (data["unit_id"] != unit["unit_id"] or data["job_id"] != str(job_id)
                or data["status"] != "COMPLETED"
                or data["result"]["decision"] != unit["inspection_result"]):
            raise ValueError("inspection identity or decision mismatch")
        expected_image = (f"inspections/{unit['unit_id']}/02_annotated_report.png"
                          if data["image"]["ready"] else None)
        if unit["inspection_image_path"] != expected_image:
            raise ValueError("inspection image path does not match the database")
        links = {row["slot_code"]: row["unit_defect_id"] for row in slot_rows}
        stored_links = stored["unit_defects"]
        if (len(stored_links) != len(links)
                or {row["slot_code"]: row["unit_defect_id"] for row in stored_links} != links
                or len(data["result"]["slots"]) != len(links)
                or {slot["slot_code"] for slot in data["result"]["slots"]} != set(links)):
            raise ValueError("inspection UID links do not match the database")
        for slot in data["result"]["slots"]:
            slot["unit_defect_id"] = links[slot["slot_code"]]
        return data
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise InspectionUnavailable("inspection JSON is incomplete or inconsistent") from error


def inspection(unit_id, *, root=None, dsn=None):
    """Read one archived inspection and verify its slot UID links against production."""
    try:
        with _connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM production.units WHERE unit_id = %s", (unit_id,))
            unit = cursor.fetchone()
            if unit is None:
                raise ResourceNotFound("unit was not found")
            cursor.execute("""
                SELECT ud.unit_defect_id, ud.defect_type, ps.slot_code
                FROM production.unit_defects ud JOIN production.product_slots ps USING (product_slot_id)
                WHERE ud.unit_id = %s
            """, (unit_id,))
            data = _load_inspection(unit, unit["job_id"], cursor.fetchall(), root)
    except psycopg.Error as error:
        raise DatabaseUnavailable("inspection database query failed") from error
    if data is None:
        raise ResourceNotFound("archived inspection was not found")
    return data


def inspection_image(unit_id):
    data = inspection(unit_id)
    image = data["image"]
    if not image.get("ready"):
        raise InspectionUnavailable("inspection image is not ready")
    root = _inspection_root()
    path = (root / "inspections" / str(unit_id) / "02_annotated_report.png").resolve()
    if not path.is_relative_to(root):
        raise InspectionUnavailable("inspection image path is outside storage")
    limit = int(os.environ.get("DEFECT_IMAGE_MAX_BYTES", "10485760"))
    try:
        with path.open("rb") as source:
            png = source.read(limit + 1)
    except OSError as error:
        raise InspectionUnavailable("inspection image is not available") from error
    if (len(png) > limit or len(png) != image.get("size_bytes")
            or not png.startswith(b"\x89PNG\r\n\x1a\n")
            or hashlib.sha256(png).hexdigest() != image.get("sha256")):
        raise InspectionUnavailable("inspection image size or SHA256 mismatch")
    return png


def defect_reports(product_id=None, slot_code=None, unit_defect_id=None, *, dsn=None):
    """Read confirmed defects for local report generation and product/slot browsing."""
    if product_id is not None and not _all(
            "SELECT 1 FROM production.products WHERE product_id = %s", (product_id,), dsn=dsn):
        raise ResourceNotFound("product was not found")
    return _all("""
        SELECT ud.unit_defect_id, u.unit_id, u.job_id, u.inspected_at,
               ps.slot_code, ps.part_id, ud.defect_type,
               delivery.delivery_status, delivery.sent_at
        FROM production.unit_defects ud
        JOIN production.units u USING (unit_id)
        JOIN production.jobs j USING (job_id)
        JOIN production.product_slots ps USING (product_slot_id)
        LEFT JOIN production.defect_report_deliveries delivery USING (unit_defect_id)
        WHERE u.inspection_result = 'FAIL'
          AND ud.defect_type IS NOT NULL
          AND (%s::bigint IS NULL OR j.product_id = %s)
          AND (%s::text IS NULL OR ps.slot_code = %s)
          AND (%s::bigint IS NULL OR ud.unit_defect_id = %s)
        ORDER BY u.inspected_at DESC, ud.unit_defect_id DESC
    """, (product_id, product_id, slot_code, slot_code, unit_defect_id, unit_defect_id), dsn=dsn)
