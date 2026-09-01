-- Mock-only UI/API history sample. Run after production_schema.sql and 004_mock_seed.sql.
-- This file is idempotent: it adds each sample recipe once and decrements stock only
-- for the completed units inserted by that run.
\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SELECT pg_advisory_xact_lock(hashtext('production.mock_sample_data.v1'));

CREATE TEMP TABLE mock_sample_jobs (
    recipe_version text PRIMARY KEY,
    requested_quantity integer NOT NULL,
    job_status text NOT NULL,
    requested_at timestamptz NOT NULL,
    job_started_at timestamptz NOT NULL,
    job_finished_at timestamptz NOT NULL
) ON COMMIT DROP;

INSERT INTO mock_sample_jobs VALUES
    ('mock-sample-pass-202608-r1', 2, 'COMPLETED',
     TIMESTAMPTZ '2026-08-08 09:00:00+09', TIMESTAMPTZ '2026-08-08 09:01:00+09', TIMESTAMPTZ '2026-08-08 09:25:00+09'),
    ('mock-sample-fail-202608-r1', 2, 'COMPLETED',
     TIMESTAMPTZ '2026-08-12 13:00:00+09', TIMESTAMPTZ '2026-08-12 13:01:00+09', TIMESTAMPTZ '2026-08-12 13:28:00+09'),
    ('mock-sample-assembly-failed-202608-r1', 1, 'FAILED',
     TIMESTAMPTZ '2026-08-16 15:00:00+09', TIMESTAMPTZ '2026-08-16 15:01:00+09', TIMESTAMPTZ '2026-08-16 15:05:00+09');

CREATE TEMP TABLE mock_sample_units (
    recipe_version text NOT NULL REFERENCES mock_sample_jobs(recipe_version),
    unit_sequence_in_job integer NOT NULL,
    unit_status text NOT NULL,
    inspection_result text NOT NULL,
    inspection_image_path text,
    assembly_started_at timestamptz NOT NULL,
    assembly_completed_at timestamptz,
    inspected_at timestamptz,
    PRIMARY KEY (recipe_version, unit_sequence_in_job)
) ON COMMIT DROP;

INSERT INTO mock_sample_units VALUES
    ('mock-sample-pass-202608-r1', 1, 'COMPLETED', 'PASS', 'InspectionSamples/mock-pass.jpg',
     TIMESTAMPTZ '2026-08-08 09:02:00+09', TIMESTAMPTZ '2026-08-08 09:12:00+09', TIMESTAMPTZ '2026-08-08 09:14:00+09'),
    ('mock-sample-pass-202608-r1', 2, 'COMPLETED', 'PASS', 'InspectionSamples/mock-pass.jpg',
     TIMESTAMPTZ '2026-08-08 09:14:30+09', TIMESTAMPTZ '2026-08-08 09:23:00+09', TIMESTAMPTZ '2026-08-08 09:24:00+09'),
    ('mock-sample-fail-202608-r1', 1, 'COMPLETED', 'FAIL', 'InspectionSamples/mock-fail.jpg',
     TIMESTAMPTZ '2026-08-12 13:02:00+09', TIMESTAMPTZ '2026-08-12 13:12:00+09', TIMESTAMPTZ '2026-08-12 13:14:00+09'),
    ('mock-sample-fail-202608-r1', 2, 'COMPLETED', 'FAIL', 'InspectionSamples/mock-fail.jpg',
     TIMESTAMPTZ '2026-08-12 13:15:00+09', TIMESTAMPTZ '2026-08-12 13:26:00+09', TIMESTAMPTZ '2026-08-12 13:27:00+09'),
    ('mock-sample-assembly-failed-202608-r1', 1, 'FAILED', 'PENDING', NULL,
     TIMESTAMPTZ '2026-08-16 15:02:00+09', NULL, NULL);

CREATE TEMP TABLE mock_sample_defects (
    recipe_version text NOT NULL,
    unit_sequence_in_job integer NOT NULL,
    slot_code text NOT NULL,
    defect_type text NOT NULL,
    PRIMARY KEY (recipe_version, unit_sequence_in_job, slot_code)
) ON COMMIT DROP;

INSERT INTO mock_sample_defects VALUES
    ('mock-sample-fail-202608-r1', 1, 'HBM-01', 'MISSING'),
    ('mock-sample-fail-202608-r1', 2, 'PM-01', 'POSITION_ERROR');

CREATE TEMP TABLE mock_sample_inserted_jobs (
    recipe_version text PRIMARY KEY,
    job_id bigint NOT NULL
) ON COMMIT DROP;

DO $$
DECLARE
    sample_product_id bigint;
BEGIN
    SELECT product_id
      INTO STRICT sample_product_id
      FROM production.products
     WHERE product_code = 'HBM-ACCELERATOR-PACKAGE-BOARD'
       AND product_version = 'hbm-pkg-r1';

    IF NOT EXISTS (
        SELECT 1 FROM production.product_slots WHERE product_id = sample_product_id
    ) THEN
        RAISE EXCEPTION 'HBM mock product has no product_slots';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM (VALUES ('HBM-01', 'HBM'), ('PM-01', 'PM')) expected(slot_code, part_id)
          LEFT JOIN production.product_slots slot
            ON slot.product_id = sample_product_id
           AND slot.slot_code = expected.slot_code
         WHERE slot.part_id IS DISTINCT FROM expected.part_id
    ) THEN
        RAISE EXCEPTION 'HBM mock product is missing the required HBM-01/PM-01 slot mapping';
    END IF;

    IF EXISTS (
        SELECT recipe_version
          FROM production.jobs
         WHERE product_id = sample_product_id
           AND recipe_version IN (SELECT recipe_version FROM mock_sample_jobs)
         GROUP BY recipe_version
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Mock sample recipe version is already duplicated';
    END IF;

    IF EXISTS (
        WITH completed_units_needed AS (
            SELECT count(*)::integer AS unit_count
              FROM mock_sample_units unit_seed
              JOIN mock_sample_jobs job_seed USING (recipe_version)
              LEFT JOIN production.jobs existing
                ON existing.product_id = sample_product_id
               AND existing.recipe_version = unit_seed.recipe_version
             WHERE existing.job_id IS NULL
               AND unit_seed.unit_status = 'COMPLETED'
        ), required_stock AS (
            SELECT slot.part_id, count(*) * (SELECT unit_count FROM completed_units_needed) AS quantity
              FROM production.product_slots slot
             WHERE slot.product_id = sample_product_id
             GROUP BY slot.part_id
        )
        SELECT 1
          FROM required_stock requirement
          JOIN production.parts part USING (part_id)
         WHERE part.stock_quantity < requirement.quantity
    ) THEN
        RAISE EXCEPTION 'Insufficient stock for new mock sample completed units';
    END IF;
END
$$;

WITH product AS (
    SELECT product_id
      FROM production.products
     WHERE product_code = 'HBM-ACCELERATOR-PACKAGE-BOARD'
       AND product_version = 'hbm-pkg-r1'
), inserted AS (
    INSERT INTO production.jobs (
        product_id, requested_quantity, recipe_version, job_status,
        requested_at, job_started_at, job_finished_at
    )
    SELECT product.product_id, sample.requested_quantity, sample.recipe_version,
           sample.job_status, sample.requested_at, sample.job_started_at,
           sample.job_finished_at
      FROM mock_sample_jobs sample
      CROSS JOIN product
     WHERE NOT EXISTS (
        SELECT 1
          FROM production.jobs existing
         WHERE existing.product_id = product.product_id
           AND existing.recipe_version = sample.recipe_version
     )
    RETURNING job_id, recipe_version
)
INSERT INTO mock_sample_inserted_jobs (recipe_version, job_id)
SELECT recipe_version, job_id FROM inserted;

CREATE TEMP TABLE mock_sample_inserted_units (
    recipe_version text NOT NULL,
    unit_sequence_in_job integer NOT NULL,
    unit_id bigint NOT NULL,
    PRIMARY KEY (recipe_version, unit_sequence_in_job)
) ON COMMIT DROP;

WITH inserted AS (
    INSERT INTO production.units (
        job_id, unit_sequence_in_job, unit_status, inspection_result,
        inspection_image_path, assembly_started_at, assembly_completed_at, inspected_at
    )
    SELECT job.job_id, unit_seed.unit_sequence_in_job, unit_seed.unit_status,
           unit_seed.inspection_result, unit_seed.inspection_image_path,
           unit_seed.assembly_started_at,
           unit_seed.assembly_completed_at, unit_seed.inspected_at
      FROM mock_sample_units unit_seed
      JOIN mock_sample_inserted_jobs job USING (recipe_version)
    RETURNING unit_id, job_id, unit_sequence_in_job
)
INSERT INTO mock_sample_inserted_units (recipe_version, unit_sequence_in_job, unit_id)
SELECT job.recipe_version, inserted.unit_sequence_in_job, inserted.unit_id
  FROM inserted
  JOIN mock_sample_inserted_jobs job USING (job_id);

UPDATE production.units unit
   SET inspection_image_path = unit_seed.inspection_image_path
  FROM production.jobs job
  JOIN production.products product ON product.product_id = job.product_id
  JOIN mock_sample_units unit_seed ON unit_seed.recipe_version = job.recipe_version
 WHERE unit.job_id = job.job_id
   AND unit.unit_sequence_in_job = unit_seed.unit_sequence_in_job
   AND product.product_code = 'HBM-ACCELERATOR-PACKAGE-BOARD'
   AND product.product_version = 'hbm-pkg-r1'
   AND unit.inspection_image_path IS DISTINCT FROM unit_seed.inspection_image_path;

INSERT INTO production.unit_defects (unit_id, product_slot_id, defect_type)
SELECT unit.unit_id, slot.product_slot_id, defect.defect_type
  FROM mock_sample_defects defect
  JOIN mock_sample_inserted_units unit
    ON unit.recipe_version = defect.recipe_version
   AND unit.unit_sequence_in_job = defect.unit_sequence_in_job
  JOIN production.products product
    ON product.product_code = 'HBM-ACCELERATOR-PACKAGE-BOARD'
   AND product.product_version = 'hbm-pkg-r1'
  JOIN production.product_slots slot
    ON slot.product_id = product.product_id
   AND slot.slot_code = defect.slot_code;

WITH consumption AS (
    SELECT unit.unit_id,
           slot.part_id,
           count(*)::integer AS quantity,
           unit.assembly_completed_at
      FROM production.units unit
      JOIN mock_sample_inserted_jobs job USING (job_id)
      JOIN production.jobs production_job ON production_job.job_id = unit.job_id
      JOIN production.product_slots slot
        ON slot.product_id = production_job.product_id
     WHERE unit.unit_status = 'COMPLETED'
     GROUP BY unit.unit_id, slot.part_id, unit.assembly_completed_at
), movement AS (
    INSERT INTO production.inventory_movements (
        part_id, quantity_delta, movement_type, unit_id, reason, recorded_at
    )
    SELECT part_id, -quantity, 'CONSUMPTION', unit_id,
           'MOCK_SAMPLE_COMPLETION', assembly_completed_at
      FROM consumption
    RETURNING part_id, -quantity_delta AS quantity
), requirement AS (
    SELECT part_id, sum(quantity)::integer AS quantity
      FROM movement
     GROUP BY part_id
)
UPDATE production.parts part
   SET stock_quantity = part.stock_quantity - requirement.quantity
  FROM requirement
 WHERE part.part_id = requirement.part_id
   AND requirement.quantity > 0;

COMMIT;
