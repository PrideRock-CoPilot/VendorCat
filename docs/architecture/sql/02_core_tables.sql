-- Core table starter set for single schema vendor_prod.twvendor
-- Expand types and constraints during detailed design.

-- Source immutable tables
CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.src_ingest_batch (
  batch_id STRING NOT NULL,
  source_system STRING NOT NULL,
  source_object STRING NOT NULL,
  extract_ts TIMESTAMP NOT NULL,
  loaded_ts TIMESTAMP NOT NULL,
  row_count BIGINT,
  status STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.src_peoplesoft_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts TIMESTAMP NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.src_zycus_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts TIMESTAMP NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.src_spreadsheet_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts TIMESTAMP NOT NULL,
  file_name STRING NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
) USING DELTA;

-- Canonical current-state tables
CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor (
  vendor_id STRING NOT NULL,
  legal_name STRING NOT NULL,
  display_name STRING,
  lifecycle_state STRING NOT NULL,
  owner_org_id STRING NOT NULL,
  risk_tier STRING,
  source_system STRING,
  source_record_id STRING,
  source_batch_id STRING,
  source_extract_ts TIMESTAMP,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_identifier (
  vendor_identifier_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  identifier_type STRING NOT NULL,
  identifier_value STRING NOT NULL,
  is_primary BOOLEAN NOT NULL,
  country_code STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_contact (
  vendor_contact_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  contact_type STRING NOT NULL,
  full_name STRING NOT NULL,
  email STRING,
  phone STRING,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_org_assignment (
  vendor_org_assignment_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  org_id STRING NOT NULL,
  assignment_type STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_business_owner (
  vendor_owner_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  owner_user_principal STRING NOT NULL,
  owner_role STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_offering (
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_name STRING NOT NULL,
  offering_type STRING,
  lifecycle_state STRING NOT NULL,
  criticality_tier STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_offering_business_owner (
  offering_owner_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  owner_user_principal STRING NOT NULL,
  owner_role STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_offering_contact (
  offering_contact_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  contact_type STRING NOT NULL,
  full_name STRING NOT NULL,
  email STRING,
  phone STRING,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_contract (
  contract_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_id STRING,
  contract_number STRING,
  contract_status STRING NOT NULL,
  start_date DATE,
  end_date DATE,
  cancelled_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_contract_event (
  contract_event_id STRING NOT NULL,
  contract_id STRING NOT NULL,
  event_type STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  reason_code STRING,
  notes STRING,
  actor_user_principal STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_demo (
  demo_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_id STRING,
  demo_date DATE NOT NULL,
  overall_score DECIMAL(5,2),
  selection_outcome STRING NOT NULL,
  non_selection_reason_code STRING,
  notes STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_demo_score (
  demo_score_id STRING NOT NULL,
  demo_id STRING NOT NULL,
  score_category STRING NOT NULL,
  score_value DECIMAL(5,2) NOT NULL,
  weight DECIMAL(5,2),
  comments STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.core_vendor_demo_note (
  demo_note_id STRING NOT NULL,
  demo_id STRING NOT NULL,
  note_type STRING NOT NULL,
  note_text STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL
) USING DELTA;

-- History and audit
CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.hist_vendor (
  vendor_hist_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  version_no BIGINT NOT NULL,
  valid_from_ts TIMESTAMP NOT NULL,
  valid_to_ts TIMESTAMP,
  is_current BOOLEAN NOT NULL,
  snapshot_json STRING NOT NULL,
  changed_by STRING NOT NULL,
  change_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.hist_vendor_offering (
  vendor_offering_hist_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  version_no BIGINT NOT NULL,
  valid_from_ts TIMESTAMP NOT NULL,
  valid_to_ts TIMESTAMP,
  is_current BOOLEAN NOT NULL,
  snapshot_json STRING NOT NULL,
  changed_by STRING NOT NULL,
  change_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.hist_contract (
  contract_hist_id STRING NOT NULL,
  contract_id STRING NOT NULL,
  version_no BIGINT NOT NULL,
  valid_from_ts TIMESTAMP NOT NULL,
  valid_to_ts TIMESTAMP,
  is_current BOOLEAN NOT NULL,
  snapshot_json STRING NOT NULL,
  changed_by STRING NOT NULL,
  change_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.audit_entity_change (
  change_event_id STRING NOT NULL,
  entity_name STRING NOT NULL,
  entity_id STRING NOT NULL,
  action_type STRING NOT NULL,
  before_json STRING,
  after_json STRING,
  actor_user_principal STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  request_id STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.audit_workflow_event (
  workflow_event_id STRING NOT NULL,
  workflow_type STRING NOT NULL,
  workflow_id STRING NOT NULL,
  old_status STRING,
  new_status STRING,
  actor_user_principal STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  notes STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.audit_access_event (
  access_event_id STRING NOT NULL,
  actor_user_principal STRING NOT NULL,
  action_type STRING NOT NULL,
  target_user_principal STRING,
  target_role STRING,
  event_ts TIMESTAMP NOT NULL,
  notes STRING
) USING DELTA;

-- App workflow tables
CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.app_onboarding_request (
  request_id STRING NOT NULL,
  requestor_user_principal STRING NOT NULL,
  vendor_name_raw STRING NOT NULL,
  priority STRING,
  status STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.app_vendor_change_request (
  change_request_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  requestor_user_principal STRING NOT NULL,
  change_type STRING NOT NULL,
  requested_payload_json STRING NOT NULL,
  status STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.app_onboarding_task (
  task_id STRING NOT NULL,
  request_id STRING NOT NULL,
  task_type STRING NOT NULL,
  assignee_group STRING,
  due_at TIMESTAMP,
  status STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.app_onboarding_approval (
  approval_id STRING NOT NULL,
  request_id STRING NOT NULL,
  stage_name STRING NOT NULL,
  approver_user_principal STRING,
  decision STRING,
  decided_at TIMESTAMP,
  comments STRING,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.app_access_request (
  access_request_id STRING NOT NULL,
  requester_user_principal STRING NOT NULL,
  requested_role STRING NOT NULL,
  justification STRING,
  status STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.app_note (
  note_id STRING NOT NULL,
  entity_name STRING NOT NULL,
  entity_id STRING NOT NULL,
  note_type STRING NOT NULL,
  note_text STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL
) USING DELTA;

-- Security tables
CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.sec_user_role_map (
  user_principal STRING NOT NULL,
  role_code STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  granted_by STRING NOT NULL,
  granted_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.sec_user_org_scope (
  user_principal STRING NOT NULL,
  org_id STRING NOT NULL,
  scope_level STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  granted_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_prod.twvendor.sec_role_permission (
  role_code STRING NOT NULL,
  object_name STRING NOT NULL,
  action_code STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;
