-- Add the pre-claim request withdrawal boundary to an existing production DB.
\set ON_ERROR_STOP on

BEGIN;

CREATE OR REPLACE FUNCTION production.cancel_pending_job(target_job_id uuid)
RETURNS TABLE(job_id uuid, job_status text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, production
AS $$
    UPDATE production.jobs AS job
       SET job_status = 'CANCELLED', job_finished_at = now()
     WHERE job.job_id = target_job_id
       AND job.job_status = 'PENDING'
    RETURNING job.job_id, job.job_status
$$;

REVOKE ALL ON FUNCTION production.cancel_pending_job(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION production.cancel_pending_job(uuid) TO job_submitter;

COMMIT;
