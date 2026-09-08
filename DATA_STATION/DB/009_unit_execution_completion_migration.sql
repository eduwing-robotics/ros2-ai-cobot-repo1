-- Inspection evidence survives transfer failure; completion belongs to the full workflow.
BEGIN;
ALTER TABLE production.units DROP CONSTRAINT ck_units_inspected;
ALTER TABLE production.units ADD CONSTRAINT ck_units_inspected CHECK (
        (inspection_result = 'PENDING' AND unit_status IN ('RUNNING', 'FAILED')
         AND inspected_at IS NULL)
        OR
        (inspection_result IN ('PASS', 'FAIL')
         AND assembly_completed_at IS NOT NULL
         AND inspected_at IS NOT NULL)
        OR
        (inspection_result = 'UNKNOWN'
         AND unit_status IN ('RUNNING', 'FAILED')
         AND assembly_completed_at IS NOT NULL
         AND inspected_at IS NOT NULL)
    );
COMMIT;
