-- Preserve existing inspection records while allowing all product slots to be stored.
BEGIN;

ALTER TABLE production.units DROP CONSTRAINT ck_units_inspection;
ALTER TABLE production.units ADD CONSTRAINT ck_units_inspection
    CHECK (inspection_result IN ('PENDING', 'PASS', 'FAIL', 'UNKNOWN'));

ALTER TABLE production.units DROP CONSTRAINT ck_units_inspected;
ALTER TABLE production.units ADD CONSTRAINT ck_units_inspected CHECK (
    (inspection_result = 'PENDING' AND inspected_at IS NULL)
    OR
    (inspection_result IN ('PASS', 'FAIL')
     AND unit_status = 'COMPLETED'
     AND assembly_completed_at IS NOT NULL
     AND inspected_at IS NOT NULL)
    OR
    -- Restart recovery can fail a held Unit without discarding its UNKNOWN result.
    (inspection_result = 'UNKNOWN'
     AND unit_status IN ('RUNNING', 'FAILED')
     AND assembly_completed_at IS NOT NULL
     AND inspected_at IS NOT NULL)
);

ALTER TABLE production.unit_defects ALTER COLUMN defect_type DROP NOT NULL;
ALTER TABLE production.unit_defects DROP CONSTRAINT ck_unit_defects_type;
ALTER TABLE production.unit_defects ADD CONSTRAINT ck_unit_defects_type CHECK (
    defect_type IN ('MISSING', 'POSITION_ERROR', 'ORIENTATION_ERROR', 'CRACK',
                    'SEATING_ERROR', 'UNCLASSIFIED_ANOMALY')
);

COMMIT;
