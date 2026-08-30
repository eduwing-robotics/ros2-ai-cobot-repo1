-- Run after production_schema.sql and 002_query_samples.sql in the same psql session.
-- All test rows are rolled back.

BEGIN;

INSERT INTO production.parts (
    part_id, part_name, part_category, stock_quantity
) VALUES (
    '__DATASTATION_TEST_PART__', 'test-part', 'TEST', 2
);

INSERT INTO production.products (
    product_id,
    product_code,
    product_name,
    product_version,
    is_selectable,
    definition_locked_at
) VALUES (
    -1001,
    '__DATASTATION_TEST_PRODUCT__',
    'DataStation smoke product',
    'test-v1',
    true,
    '2026-01-01T00:00:00Z'
);

INSERT INTO production.product_slots (
    product_slot_id, product_id, slot_code, part_id
) VALUES (
    -5001, -1001, 'TEST-01', '__DATASTATION_TEST_PART__'
);

INSERT INTO production.jobs (
    job_id,
    product_id,
    requested_quantity,
    recipe_version,
    job_status,
    requested_at,
    job_started_at,
    job_finished_at
) VALUES (
    -7001,
    -1001,
    3,
    '__DATASTATION_TEST_PRODUCT__-test-v1-R1',
    'COMPLETED',
    '2026-01-01T00:00:00Z',
    '2026-01-01T00:01:00Z',
    '2026-01-01T00:40:00Z'
);

INSERT INTO production.units (
    unit_id,
    job_id,
    unit_sequence_in_job,
    unit_status,
    inspection_result,
    assembly_started_at,
    assembly_completed_at,
    inspected_at
) VALUES
    (-8001, -7001, 1, 'COMPLETED', 'PASS',
     '2026-01-01T00:01:00Z', '2026-01-01T00:10:00Z', '2026-01-01T00:11:00Z'),
    (-8002, -7001, 2, 'COMPLETED', 'FAIL',
     '2026-01-01T00:12:00Z', '2026-01-01T00:20:00Z', '2026-01-01T00:21:00Z'),
    (-8003, -7001, 3, 'COMPLETED', 'PASS',
     '2026-01-01T00:22:00Z', '2026-01-01T00:30:00Z', '2026-01-01T00:31:00Z');

INSERT INTO production.unit_defects (
    unit_defect_id, unit_id, product_slot_id, defect_type
) VALUES (
    -9001, -8002, -5001, 'CRACK'
);

DO $$
DECLARE
    inspected bigint;
    defective bigint;
    defect_rate numeric;
    shortage bigint;
BEGIN
    SELECT COUNT(u.unit_id),
           COUNT(ud.unit_defect_id),
           ROUND(
               100.0 * COUNT(ud.unit_defect_id)
               / NULLIF(COUNT(u.unit_id), 0),
               2
           )
      INTO inspected, defective, defect_rate
    FROM production.product_slots ps
    JOIN production.jobs j ON j.product_id = ps.product_id
    JOIN production.units u
      ON u.job_id = j.job_id
     AND u.inspection_result IN ('PASS', 'FAIL')
    LEFT JOIN production.unit_defects ud
      ON ud.unit_id = u.unit_id
     AND ud.product_slot_id = ps.product_slot_id
    WHERE ps.product_id = -1001;

    SELECT GREATEST(COUNT(*) * 3 - p.stock_quantity, 0)
      INTO shortage
    FROM production.product_slots ps
    JOIN production.parts p ON p.part_id = ps.part_id
    WHERE ps.product_id = -1001
    GROUP BY p.part_id, p.stock_quantity;

    IF inspected <> 3 OR defective <> 1 OR defect_rate <> 33.33 THEN
        RAISE EXCEPTION
            'slot-rate check failed: inspected=%, defective=%, rate=%',
            inspected, defective, defect_rate;
    END IF;

    IF shortage <> 1 THEN
        RAISE EXCEPTION 'requirement check failed: shortage=%', shortage;
    END IF;
END
$$;

EXECUTE datastation_product(-1001);
EXECUTE datastation_product_requirements(-1001, 3);
EXECUTE datastation_job(-7001);
EXECUTE datastation_slot_rates(-1001);
EXECUTE datastation_part_rates(
    '2026-01-01T00:00:00Z',
    '2026-01-02T00:00:00Z'
);

ROLLBACK;
