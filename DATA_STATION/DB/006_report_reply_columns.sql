-- Migration for databases created before the countermeasure form was revised.
-- 001_schema.sql only has CREATE TABLE IF NOT EXISTS, so an existing database
-- never picks up new columns. Run this once per existing database.
--
--   psql -v ON_ERROR_STOP=1 -d main_unity_mock -f DATA_STATION/DB/006_report_reply_columns.sql
--
-- Idempotent: safe to run twice. A fresh database created from 001_schema.sql
-- already has everything here and this file becomes a no-op.

BEGIN;
SET LOCAL lock_timeout = '5s';

-- part_id -> group_id. Without it the countermeasure form cannot fill the
-- 「대체품」 sheet or the 「판단자료 D」 checklist.
CREATE TABLE IF NOT EXISTS part_catalog.part_group_links (
    part_id text PRIMARY KEY,
    group_id text NOT NULL REFERENCES part_catalog.part_groups(group_id),
    load_id bigint NOT NULL REFERENCES part_catalog.datasheet_loads(load_id)
);

CREATE INDEX IF NOT EXISTS ix_part_group_links_group
    ON part_catalog.part_group_links(group_id);

-- Datasheet 'defect relevance' note, filled by a person. Empty prints as 미평가.
ALTER TABLE part_catalog.part_candidates
    ADD COLUMN IF NOT EXISTS defect_relevance text;

-- The assignee's reply. root_cause_summary alone collapsed ① ② ③ ⑥ into one
-- column, so a repeat defect could not read back what was done last time.
ALTER TABLE defect_report.alert_countermeasures
    ADD COLUMN IF NOT EXISTS containment_summary text,
    ADD COLUMN IF NOT EXISTS escape_cause_summary text,
    ADD COLUMN IF NOT EXISTS closure_note text,
    ADD COLUMN IF NOT EXISTS closed_by text;

COMMIT;
