-- PostgreSQL prepared-query samples for the DataStation read-only server.
-- Run once per dedicated connection, or copy each SELECT body into the DB driver.
-- The HTTP layer must validate IDs, positive quantities, date ranges, limit and offset.

-- GET /health
PREPARE datastation_health AS
SELECT current_database() AS database_name,
       now() AS database_time;

-- GET /products
PREPARE datastation_products AS
WITH required_parts AS (
    SELECT product_id, part_id, COUNT(*) AS quantity_per_product
    FROM production.product_slots
    GROUP BY product_id, part_id
)
SELECT pr.product_id,
       pr.product_code,
       pr.product_name,
       pr.product_version,
       pr.is_selectable,
       COALESCE(
           MIN(FLOOR(p.stock_quantity::numeric / rp.quantity_per_product)),
           0
       )::bigint AS buildable_quantity
FROM production.products pr
LEFT JOIN required_parts rp ON rp.product_id = pr.product_id
LEFT JOIN production.parts p ON p.part_id = rp.part_id
WHERE pr.is_selectable
GROUP BY pr.product_id,
         pr.product_code,
         pr.product_name,
         pr.product_version,
         pr.is_selectable
ORDER BY pr.product_code, pr.product_version;

-- GET /products/{product_id}
PREPARE datastation_product(bigint) AS
SELECT pr.product_id,
       pr.product_code,
       pr.product_name,
       pr.product_version,
       pr.is_selectable,
       ps.product_slot_id,
       ps.slot_code,
       p.part_id,
       p.part_name,
       p.part_category,
       p.stock_quantity
FROM production.products pr
LEFT JOIN production.product_slots ps ON ps.product_id = pr.product_id
LEFT JOIN production.parts p ON p.part_id = ps.part_id
WHERE pr.product_id = $1
ORDER BY ps.slot_code;

-- GET /products/{product_id}/requirements?quantity={quantity}
PREPARE datastation_product_requirements(bigint, integer) AS
SELECT p.part_id,
       p.part_name,
       p.part_category,
       COUNT(*) AS quantity_per_product,
       COUNT(*) * $2 AS required_quantity,
       p.stock_quantity,
       GREATEST(COUNT(*) * $2 - p.stock_quantity, 0) AS shortage_quantity
FROM production.product_slots ps
JOIN production.parts p ON p.part_id = ps.part_id
WHERE ps.product_id = $1
GROUP BY p.part_id, p.part_name, p.part_category, p.stock_quantity
ORDER BY p.part_id;

-- GET /jobs/{job_id}
PREPARE datastation_job(bigint) AS
SELECT j.job_id,
       j.product_id,
       pr.product_code,
       pr.product_version,
       j.recipe_version,
       j.job_status,
       j.requested_quantity,
       COUNT(u.unit_id) FILTER (
           WHERE u.unit_status = 'COMPLETED'
       ) AS completed_quantity,
       COUNT(u.unit_id) FILTER (
           WHERE u.unit_status = 'RUNNING'
       ) AS running_quantity,
       COUNT(u.unit_id) FILTER (
           WHERE u.unit_status = 'FAILED'
       ) AS failed_quantity,
       ROUND(
           100.0 * COUNT(u.unit_id) FILTER (
               WHERE u.unit_status = 'COMPLETED'
           ) / j.requested_quantity,
           2
       ) AS progress_percent,
       j.requested_at,
       j.job_started_at,
       j.job_finished_at
FROM production.jobs j
JOIN production.products pr ON pr.product_id = j.product_id
LEFT JOIN production.units u ON u.job_id = j.job_id
WHERE j.job_id = $1
GROUP BY j.job_id,
         j.product_id,
         pr.product_code,
         pr.product_version,
         j.recipe_version,
         j.job_status,
         j.requested_quantity,
         j.requested_at,
         j.job_started_at,
         j.job_finished_at;

-- Inspection and defect history for a product.
PREPARE datastation_product_defects(bigint) AS
SELECT u.unit_id,
       u.inspected_at,
       pr.product_code,
       pr.product_version,
       ps.slot_code,
       p.part_id,
       p.part_name,
       ud.defect_type,
       u.inspection_image_path
FROM production.unit_defects ud
JOIN production.units u ON u.unit_id = ud.unit_id
JOIN production.jobs j ON j.job_id = u.job_id
JOIN production.products pr ON pr.product_id = j.product_id
JOIN production.product_slots ps
  ON ps.product_slot_id = ud.product_slot_id
JOIN production.parts p ON p.part_id = ps.part_id
WHERE j.product_id = $1
ORDER BY u.inspected_at DESC, u.unit_id DESC, ps.slot_code;

-- GET /quality/slot-rates?product_id={product_id}
-- Starts from every product slot so a zero-defect slot remains in the result.
PREPARE datastation_slot_rates(bigint) AS
SELECT ps.product_slot_id,
       ps.slot_code,
       p.part_id,
       p.part_name,
       COUNT(u.unit_id) AS inspected_quantity,
       COUNT(ud.unit_defect_id) AS defective_quantity,
       ROUND(
           100.0 * COUNT(ud.unit_defect_id)
           / NULLIF(COUNT(u.unit_id), 0),
           2
       ) AS defect_rate_percent
FROM production.product_slots ps
JOIN production.parts p ON p.part_id = ps.part_id
LEFT JOIN production.jobs j ON j.product_id = ps.product_id
LEFT JOIN production.units u
       ON u.job_id = j.job_id
      AND u.inspection_result IN ('PASS', 'FAIL')
LEFT JOIN production.unit_defects ud
       ON ud.unit_id = u.unit_id
      AND ud.product_slot_id = ps.product_slot_id
WHERE ps.product_id = $1
GROUP BY ps.product_slot_id, ps.slot_code, p.part_id, p.part_name
ORDER BY ps.slot_code;

-- GET /quality/part-rates?period_start={time}&period_end={time}
PREPARE datastation_part_rates(timestamptz, timestamptz) AS
WITH inspected AS (
    SELECT ps.part_id,
           COUNT(*) AS inspected_quantity,
           COUNT(DISTINCT u.unit_id) AS inspected_unit_quantity
    FROM production.jobs j
    JOIN production.units u ON u.job_id = j.job_id
    JOIN production.product_slots ps ON ps.product_id = j.product_id
    WHERE u.inspection_result IN ('PASS', 'FAIL')
      AND u.inspected_at >= $1
      AND u.inspected_at < $2
    GROUP BY ps.part_id
),
defective AS (
    SELECT ps.part_id, COUNT(*) AS defective_quantity
    FROM production.unit_defects ud
    JOIN production.units u ON u.unit_id = ud.unit_id
    JOIN production.product_slots ps
      ON ps.product_slot_id = ud.product_slot_id
    WHERE u.inspection_result IN ('PASS', 'FAIL')
      AND u.inspected_at >= $1
      AND u.inspected_at < $2
    GROUP BY ps.part_id
)
SELECT p.part_id,
       p.part_name,
       p.part_category,
       i.inspected_quantity,
       i.inspected_unit_quantity,
       COALESCE(d.defective_quantity, 0) AS defective_quantity,
       ROUND(
           100.0 * COALESCE(d.defective_quantity, 0)
           / NULLIF(i.inspected_quantity, 0),
           4
       ) AS defect_rate_percent
FROM inspected i
JOIN production.parts p ON p.part_id = i.part_id
LEFT JOIN defective d ON d.part_id = i.part_id
ORDER BY defect_rate_percent DESC, p.part_id;


-- Example calls:
-- EXECUTE datastation_health;
-- EXECUTE datastation_product(1001);
-- EXECUTE datastation_product_requirements(1001, 3);
-- EXECUTE datastation_job(7001);
-- EXECUTE datastation_part_rates('2026-08-01T00:00:00Z', '2026-09-01T00:00:00Z');
