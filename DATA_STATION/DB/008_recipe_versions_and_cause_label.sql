-- Sources for the two auto-generated sentences that had none.
--
-- 「대책서」 block 2 (auto_analysis) line ② prints "변경 내용 '{change}'" and
-- line ③ prints "CLOSED 대책서 {n}건({date} · {cause})". Neither value existed:
--   ② production.jobs only carries recipe_version text -- no change note, no
--     applied_at. The sentence was stating a fact the database does not hold.
--   ③ {cause} was a one-line squeeze of alert_countermeasures.root_cause_summary,
--     which is a multi-sentence paragraph. Shortening it is summarisation.
--
-- Neither is computable, so both become fields a person fills in. Without these
-- the scanner cannot emit ② and ③ without inventing text.
--
--   psql -v ON_ERROR_STOP=1 -d main_unity_mock -f DATA_STATION/DB/008_recipe_versions_and_cause_label.sql
--
-- Idempotent. A fresh database created from 001_schema.sql already has this.

BEGIN;
SET LOCAL lock_timeout = '5s';

-- What changed in each recipe version, and when it went live.
-- Deliberately not referenced by a foreign key from production.jobs: a job may
-- run a version nobody registered yet, and report issue must not block on it.
-- The scanner LEFT JOINs and drops the '변경 내용' clause when there is no row.
CREATE TABLE IF NOT EXISTS production.recipe_versions (
    recipe_version text PRIMARY KEY,
    change_note text,
    applied_at timestamptz
);

-- One-line restatement of root_cause_summary, written by the assignee alongside
-- the ② reply. Line ③ of a LATER report reads this back, so it has to stay short
-- enough to sit inside one sentence.
ALTER TABLE defect_report.alert_countermeasures
    ADD COLUMN IF NOT EXISTS root_cause_label text;

DO $$
BEGIN
    ALTER TABLE defect_report.alert_countermeasures
        ADD CONSTRAINT ck_countermeasures_cause_label
        CHECK (root_cause_label IS NULL OR char_length(root_cause_label) <= 40);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
