-- Part render image for the countermeasure report header and the Unity UI.
-- Source: the datasheet BOM sheet's 'Image' column, one row per part_id.
-- Paths are relative to the Unity project's Assets/ (e.g. UI/Icons/item-cap.png).
--
--   psql -v ON_ERROR_STOP=1 -d main_unity_mock -f DATA_STATION/DB/007_part_image_path.sql
--
-- Idempotent. A database created from 001_schema.sql already has this column.

BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE part_catalog.part_group_links
    ADD COLUMN IF NOT EXISTS image_path text;

COMMIT;
