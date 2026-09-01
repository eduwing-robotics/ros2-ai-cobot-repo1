BEGIN;

-- Application credentials are created outside this repository. These NOLOGIN
-- roles only define the privileges granted to those deployment-specific users.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'production_writer') THEN
        CREATE ROLE production_writer NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'datastation_reader') THEN
        CREATE ROLE datastation_reader NOLOGIN;
    END IF;
END
$$;

ALTER ROLE production_writer
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE datastation_reader
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- Custom schemas and their objects must never inherit access through PUBLIC.
REVOKE ALL ON SCHEMA production FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA production
    FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA production
    FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA production
    FROM PUBLIC;

ALTER DEFAULT PRIVILEGES IN SCHEMA production
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA production
    REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA production
    REVOKE ALL ON FUNCTIONS FROM PUBLIC;

-- Reset both group roles before applying the intended least-privilege matrix.
REVOKE ALL ON SCHEMA production
    FROM production_writer, datastation_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA production
    FROM production_writer, datastation_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA production
    FROM production_writer, datastation_reader;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA production
    FROM production_writer, datastation_reader;

-- ROS2 owns production writes. Reference definitions remain read-only.
GRANT USAGE ON SCHEMA production TO production_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA production TO production_writer;
GRANT INSERT ON
    production.jobs,
    production.units,
    production.unit_defects,
    production.inventory_movements
    TO production_writer;
GRANT USAGE ON SEQUENCE
    production.jobs_job_id_seq,
    production.units_unit_id_seq,
    production.unit_defects_unit_defect_id_seq,
    production.inventory_movements_inventory_movement_id_seq
    TO production_writer;

-- Only the documented lifecycle columns may change after insertion.
GRANT UPDATE (stock_quantity)
    ON production.parts TO production_writer;
GRANT UPDATE (definition_locked_at)
    ON production.products TO production_writer;
GRANT UPDATE (job_status, job_started_at, job_finished_at)
    ON production.jobs TO production_writer;
GRANT UPDATE (
    unit_status,
    inspection_result,
    inspection_image_path,
    assembly_completed_at,
    inspected_at
) ON production.units TO production_writer;

-- DataStation can query production but cannot mutate any of them.
GRANT USAGE ON SCHEMA production
    TO datastation_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA production
    TO datastation_reader;

COMMIT;
