-- Imports V4 Operational Workflow + Mapping Approval Governance additive migration (Databricks/Delta).
-- Mirrors revisions/imports-v4-operational-workflow/sql/001_imports_v4_operational_workflow.sql.

ALTER TABLE app_import_job ADD COLUMN IF NOT EXISTS mapping_profile_id STRING;
ALTER TABLE app_import_job ADD COLUMN IF NOT EXISTS mapping_request_id STRING;
ALTER TABLE app_import_job ADD COLUMN IF NOT EXISTS context_json STRING;

ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS area_key STRING;
ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS source_group_key STRING;
ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS decision_action STRING;
ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS decision_target_id STRING;
ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS decision_payload_json STRING;
ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS decision_updated_at STRING;
ALTER TABLE app_import_stage_row ADD COLUMN IF NOT EXISTS decision_updated_by STRING;

CREATE TABLE IF NOT EXISTS app_import_review_area_state (
  import_review_area_state_id STRING,
  import_job_id STRING NOT NULL,
  area_key STRING NOT NULL,
  area_order INT NOT NULL,
  status STRING NOT NULL,
  confirmed_at STRING,
  confirmed_by STRING,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_identifier (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_mapping_profile_request (
  profile_request_id STRING,
  import_job_id STRING,
  submitted_by STRING NOT NULL,
  layout_key STRING NOT NULL,
  proposed_profile_name STRING,
  file_format STRING,
  source_system STRING,
  source_object STRING,
  source_signature STRING,
  source_fields_json STRING,
  source_target_mapping_json STRING,
  parser_options_json STRING,
  sample_rows_json STRING,
  status STRING NOT NULL,
  review_note STRING,
  reviewed_by STRING,
  reviewed_at STRING,
  approved_profile_id STRING,
  created_at STRING NOT NULL,
  updated_at STRING NOT NULL
) USING DELTA;

MERGE INTO sec_role_permission AS target
USING (
  SELECT 'vendor_admin' AS role_code, 'change_action' AS object_name, 'manage_import_mapping_profile' AS action_code
) AS source
ON lower(target.role_code) = lower(source.role_code)
  AND lower(target.object_name) = lower(source.object_name)
  AND lower(target.action_code) = lower(source.action_code)
WHEN MATCHED THEN
  UPDATE SET active_flag = true, updated_at = current_timestamp()
WHEN NOT MATCHED THEN
  INSERT (role_code, object_name, action_code, active_flag, updated_at)
  VALUES (source.role_code, source.object_name, source.action_code, true, current_timestamp());
