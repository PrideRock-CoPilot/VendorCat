-- Migration for existing deployments where app_lookup_option already exists
-- without SCD validity fields.

ALTER TABLE {fq_schema}.app_lookup_option
ADD COLUMN IF NOT EXISTS valid_from_ts TIMESTAMP;

ALTER TABLE {fq_schema}.app_lookup_option
ADD COLUMN IF NOT EXISTS valid_to_ts TIMESTAMP;

ALTER TABLE {fq_schema}.app_lookup_option
ADD COLUMN IF NOT EXISTS is_current BOOLEAN;

ALTER TABLE {fq_schema}.app_lookup_option
ADD COLUMN IF NOT EXISTS deleted_flag BOOLEAN;

UPDATE {fq_schema}.app_lookup_option
SET
  valid_from_ts = COALESCE(valid_from_ts, updated_at, current_timestamp()),
  valid_to_ts = COALESCE(valid_to_ts, TIMESTAMP('9999-12-31 23:59:59')),
  is_current = COALESCE(is_current, true),
  deleted_flag = COALESCE(
    deleted_flag,
    CASE WHEN COALESCE(active_flag, true) = false THEN true ELSE false END
  )
WHERE valid_from_ts IS NULL OR is_current IS NULL OR deleted_flag IS NULL;
