-- One-time migration from control.assembly_requests to production.jobs.
-- Stop MainServer and AssemblySequencer before running this file.
-- Linked Jobs keep request_id; unlinked Jobs receive a deterministic UUID.
-- Terminal requests without a Job are removed with the control schema.
\set ON_ERROR_STOP on

BEGIN;

LOCK TABLE control.assembly_requests, production.units, production.jobs
    IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM control.assembly_requests
         WHERE job_id IS NULL
           AND request_status IN ('QUEUED', 'RUNNING')
    ) THEN
        RAISE EXCEPTION
            'Cannot migrate: an active assembly request has no Job';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM production.jobs
         WHERE job_status IN ('PENDING', 'RUNNING')
    ) OR EXISTS (
        SELECT 1
          FROM production.units
         WHERE unit_status = 'RUNNING'
    ) THEN
        RAISE EXCEPTION
            'Cannot migrate while a Job or Unit is active';
    END IF;
END
$$;

CREATE TEMP TABLE job_id_migration (
    old_job_id bigint PRIMARY KEY,
    new_job_id uuid UNIQUE NOT NULL
) ON COMMIT DROP;

INSERT INTO job_id_migration (old_job_id, new_job_id)
SELECT job.job_id,
       COALESCE(
           request.request_id,
           md5('production.jobs:' || job.job_id::text)::uuid
       )
  FROM production.jobs job
  LEFT JOIN control.assembly_requests request
    ON request.job_id = job.job_id;

ALTER TABLE production.jobs
    ADD COLUMN job_id_uuid uuid;
UPDATE production.jobs job
   SET job_id_uuid = migration.new_job_id
  FROM job_id_migration migration
 WHERE migration.old_job_id = job.job_id;
ALTER TABLE production.jobs
    ALTER COLUMN job_id_uuid SET NOT NULL;

ALTER TABLE production.units
    ADD COLUMN job_id_uuid uuid;
UPDATE production.units unit
   SET job_id_uuid = migration.new_job_id
  FROM job_id_migration migration
 WHERE migration.old_job_id = unit.job_id;
ALTER TABLE production.units
    ALTER COLUMN job_id_uuid SET NOT NULL;

DROP TABLE control.assembly_requests;
DROP SCHEMA control;

ALTER TABLE production.units
    DROP CONSTRAINT units_job_id_fkey,
    DROP CONSTRAINT uq_units_job_sequence;
ALTER TABLE production.jobs
    DROP CONSTRAINT jobs_pkey;

DROP INDEX production.uq_jobs_single_active;
DROP INDEX production.ix_jobs_requested_at;

ALTER TABLE production.units DROP COLUMN job_id;
ALTER TABLE production.jobs DROP COLUMN job_id;
ALTER TABLE production.jobs RENAME COLUMN job_id_uuid TO job_id;
ALTER TABLE production.units RENAME COLUMN job_id_uuid TO job_id;

ALTER TABLE production.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (job_id);
ALTER TABLE production.units
    ADD CONSTRAINT units_job_id_fkey
        FOREIGN KEY (job_id) REFERENCES production.jobs(job_id),
    ADD CONSTRAINT uq_units_job_sequence
        UNIQUE (job_id, unit_sequence_in_job);

CREATE INDEX ix_jobs_queue
    ON production.jobs(requested_at)
    WHERE job_status = 'PENDING';
CREATE UNIQUE INDEX uq_jobs_single_running
    ON production.jobs ((1))
    WHERE job_status = 'RUNNING';
CREATE UNIQUE INDEX uq_units_single_running_per_job
    ON production.units(job_id)
    WHERE unit_status = 'RUNNING';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM production.units unit
          LEFT JOIN production.jobs job ON job.job_id = unit.job_id
         WHERE job.job_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Migration produced an orphan Unit';
    END IF;
END
$$;

COMMIT;
