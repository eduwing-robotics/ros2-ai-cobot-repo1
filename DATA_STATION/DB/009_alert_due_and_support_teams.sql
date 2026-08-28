-- The last auto-filled fields on the cover that had no source.
--
-- Row 9 is the reply-deadline band and prints four deadlines; the head prints
-- the supporting teams. alerts only carried initial_action_due_at and
-- final_action_due_at, so two of those values could not be filled at all.
--
--   ① initial_action_due_at   24h                        (already present)
--   ②③ cause_due_at           3~5 days                    <- added here
--   ④  final_action_due_at    1~2 weeks                   (already present)
--   ⑤  no column on purpose -- '적용 후 2~4주' is relative to applied_at,
--      which does not exist when the report is issued. It is a constant string.
--
--   psql -v ON_ERROR_STOP=1 -d main_unity_mock -f DATA_STATION/DB/009_alert_due_and_support_teams.sql
--
-- Idempotent. A fresh database created from 001_schema.sql already has this.

BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE defect_report.alerts
    ADD COLUMN IF NOT EXISTS cause_due_at timestamptz,
    ADD COLUMN IF NOT EXISTS support_teams text;

-- ①  <=  ②③  <=  ④. Only checked when both ends are present, like the
-- existing ck_alerts_due_dates.
DO $$
BEGIN
    ALTER TABLE defect_report.alerts
        ADD CONSTRAINT ck_alerts_cause_due
        CHECK (
            cause_due_at IS NULL
            OR ((initial_action_due_at IS NULL OR cause_due_at >= initial_action_due_at)
                AND (final_action_due_at IS NULL OR cause_due_at <= final_action_due_at))
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
