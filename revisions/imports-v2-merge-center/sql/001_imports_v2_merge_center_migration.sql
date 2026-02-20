-- Imports V2 + Vendor Merge Center
-- Additive migration for Databricks/Delta runtime environments.
-- Run in the target catalog/schema before deploying this release.

USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

-- 1) Vendor merge lineage columns (additive).
ALTER TABLE core_vendor ADD COLUMN IF NOT EXISTS merged_into_vendor_id STRING;
ALTER TABLE core_vendor ADD COLUMN IF NOT EXISTS merged_at STRING;
ALTER TABLE core_vendor ADD COLUMN IF NOT EXISTS merged_by STRING;
ALTER TABLE core_vendor ADD COLUMN IF NOT EXISTS merge_reason STRING;

-- 2) Shared import mapping profiles table.
CREATE TABLE IF NOT EXISTS app_import_mapping_profile (
  profile_id STRING,
  layout_key STRING NOT NULL,
  profile_name STRING NOT NULL,
  file_format STRING,
  source_signature STRING,
  source_fields_json STRING,
  source_target_mapping_json STRING,
  field_mapping_json STRING,
  parser_options_json STRING,
  active_flag BOOLEAN,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

-- 3) Backfill required admin change actions (idempotent via MERGE).
MERGE INTO sec_role_permission AS target
USING (
  SELECT 'vendor_admin' AS role_code, 'change_action' AS object_name, 'manage_import_mapping_profile' AS action_code
  UNION ALL
  SELECT 'vendor_admin' AS role_code, 'change_action' AS object_name, 'merge_vendor_records' AS action_code
) AS source
ON lower(target.role_code) = lower(source.role_code)
  AND lower(target.object_name) = lower(source.object_name)
  AND lower(target.action_code) = lower(source.action_code)
WHEN MATCHED THEN
  UPDATE SET active_flag = true, updated_at = current_timestamp()
WHEN NOT MATCHED THEN
  INSERT (role_code, object_name, action_code, active_flag, updated_at)
  VALUES (source.role_code, source.object_name, source.action_code, true, current_timestamp());

-- 4) Post-migration optimize for new/updated objects.
OPTIMIZE core_vendor;
OPTIMIZE app_import_mapping_profile;
