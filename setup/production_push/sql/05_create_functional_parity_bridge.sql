USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

-- Transitional compatibility bridge for Wave 1 parity.
-- Goal: keep current application functionality available while canonical V1 model is completed.

CREATE TABLE IF NOT EXISTS app_user_directory (
  user_id STRING,
  login_identifier STRING,
  email STRING,
  network_id STRING,
  employee_id STRING,
  manager_id STRING,
  first_name STRING,
  last_name STRING,
  display_name STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  last_seen_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_user_settings (
  setting_id STRING,
  user_principal STRING,
  setting_key STRING,
  setting_value_json STRING,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_usage_log (
  usage_event_id STRING,
  user_principal STRING,
  page_name STRING,
  event_type STRING,
  event_ts TIMESTAMP,
  payload_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS sec_role_definition (
  role_code STRING,
  role_name STRING,
  description STRING,
  approval_level INT,
  can_edit BOOLEAN,
  can_report BOOLEAN,
  can_direct_apply BOOLEAN,
  active_flag BOOLEAN,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS sec_role_permission (
  role_code STRING,
  object_name STRING,
  action_code STRING,
  active_flag BOOLEAN,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS sec_user_role_map (
  user_principal STRING,
  role_code STRING,
  active_flag BOOLEAN,
  granted_by STRING,
  granted_at TIMESTAMP,
  revoked_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS sec_group_role_map (
  group_principal STRING,
  role_code STRING,
  active_flag BOOLEAN,
  granted_by STRING,
  granted_at TIMESTAMP,
  revoked_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS sec_user_org_scope (
  user_principal STRING,
  org_id STRING,
  scope_level STRING,
  active_flag BOOLEAN,
  granted_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS audit_entity_change (
  change_event_id STRING,
  entity_name STRING,
  entity_id STRING,
  action_type STRING,
  before_json STRING,
  after_json STRING,
  actor_user_principal STRING,
  event_ts TIMESTAMP,
  request_id STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS audit_workflow_event (
  workflow_event_id STRING,
  workflow_type STRING,
  workflow_id STRING,
  old_status STRING,
  new_status STRING,
  actor_user_principal STRING,
  event_ts TIMESTAMP,
  notes STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS audit_access_event (
  access_event_id STRING,
  actor_user_principal STRING,
  action_type STRING,
  target_user_principal STRING,
  target_role STRING,
  event_ts TIMESTAMP,
  notes STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_help_article (
  article_id STRING,
  slug STRING,
  title STRING,
  section STRING,
  article_type STRING,
  role_visibility STRING,
  content_md STRING,
  owned_by STRING,
  updated_at TIMESTAMP,
  updated_by STRING,
  created_at TIMESTAMP,
  created_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_help_feedback (
  feedback_id STRING,
  article_id STRING,
  article_slug STRING,
  was_helpful BOOLEAN,
  comment STRING,
  user_principal STRING,
  page_path STRING,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_help_issue (
  issue_id STRING,
  article_id STRING,
  article_slug STRING,
  issue_title STRING,
  issue_description STRING,
  page_path STRING,
  user_principal STRING,
  created_at TIMESTAMP
) USING DELTA;