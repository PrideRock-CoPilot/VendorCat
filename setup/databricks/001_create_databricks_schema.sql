-- Databricks bootstrap for Vendor Catalog runtime objects.
-- This script is idempotent and targets a single Unity Catalog schema.

CREATE CATALOG IF NOT EXISTS {catalog};
CREATE SCHEMA IF NOT EXISTS {fq_schema};

-- Source immutable tables
CREATE TABLE IF NOT EXISTS {fq_schema}.src_ingest_batch (
  batch_id STRING NOT NULL,
  source_system STRING NOT NULL,
  source_object STRING NOT NULL,
  extract_ts TIMESTAMP NOT NULL,
  loaded_ts TIMESTAMP NOT NULL,
  row_count BIGINT,
  status STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.src_peoplesoft_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts TIMESTAMP NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.src_zycus_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts TIMESTAMP NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.src_spreadsheet_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts TIMESTAMP NOT NULL,
  file_name STRING NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at TIMESTAMP NOT NULL
) USING DELTA;

-- Canonical current-state tables
CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_identifier (
  vendor_identifier_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  identifier_type STRING NOT NULL,
  identifier_value STRING NOT NULL,
  is_primary BOOLEAN NOT NULL,
  country_code STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_contact (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_org_assignment (
  vendor_org_assignment_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  org_id STRING NOT NULL,
  assignment_type STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_business_owner (
  vendor_owner_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  owner_user_principal STRING NOT NULL,
  owner_role STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_offering (
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_name STRING NOT NULL,
  offering_type STRING,
  lob STRING,
  service_type STRING,
  lifecycle_state STRING NOT NULL,
  criticality_tier STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_offering_business_owner (
  offering_owner_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  owner_user_principal STRING NOT NULL,
  owner_role STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_offering_contact (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.core_contract (
  contract_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_id STRING,
  contract_number STRING,
  contract_status STRING NOT NULL,
  start_date DATE,
  end_date DATE,
  cancelled_flag BOOLEAN NOT NULL,
  annual_value DOUBLE,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_contract_event (
  contract_event_id STRING NOT NULL,
  contract_id STRING NOT NULL,
  event_type STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  reason_code STRING,
  notes STRING,
  actor_user_principal STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_demo (
  demo_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_id STRING,
  demo_date DATE NOT NULL,
  overall_score DOUBLE,
  selection_outcome STRING NOT NULL,
  non_selection_reason_code STRING,
  notes STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_demo_score (
  demo_score_id STRING NOT NULL,
  demo_id STRING NOT NULL,
  score_category STRING NOT NULL,
  score_value DOUBLE NOT NULL,
  weight DOUBLE,
  comments STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.core_vendor_demo_note (
  demo_note_id STRING NOT NULL,
  demo_id STRING NOT NULL,
  note_type STRING NOT NULL,
  note_text STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL
) USING DELTA;

-- History and audit
CREATE TABLE IF NOT EXISTS {fq_schema}.hist_vendor (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.hist_vendor_offering (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.hist_contract (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.audit_entity_change (
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

CREATE TABLE IF NOT EXISTS {fq_schema}.audit_workflow_event (
  workflow_event_id STRING NOT NULL,
  workflow_type STRING NOT NULL,
  workflow_id STRING NOT NULL,
  old_status STRING,
  new_status STRING,
  actor_user_principal STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  notes STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.audit_access_event (
  access_event_id STRING NOT NULL,
  actor_user_principal STRING NOT NULL,
  action_type STRING NOT NULL,
  target_user_principal STRING,
  target_role STRING,
  event_ts TIMESTAMP NOT NULL,
  notes STRING
) USING DELTA;

-- App workflow tables
CREATE TABLE IF NOT EXISTS {fq_schema}.app_onboarding_request (
  request_id STRING NOT NULL,
  requestor_user_principal STRING NOT NULL,
  vendor_name_raw STRING NOT NULL,
  priority STRING,
  status STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_vendor_change_request (
  change_request_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  requestor_user_principal STRING NOT NULL,
  change_type STRING NOT NULL,
  requested_payload_json STRING NOT NULL,
  status STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_onboarding_task (
  task_id STRING NOT NULL,
  request_id STRING NOT NULL,
  task_type STRING NOT NULL,
  assignee_group STRING,
  due_at TIMESTAMP,
  status STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_onboarding_approval (
  approval_id STRING NOT NULL,
  request_id STRING NOT NULL,
  stage_name STRING NOT NULL,
  approver_user_principal STRING,
  decision STRING,
  decided_at TIMESTAMP,
  comments STRING,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_access_request (
  access_request_id STRING NOT NULL,
  requester_user_principal STRING NOT NULL,
  requested_role STRING NOT NULL,
  justification STRING,
  status STRING NOT NULL,
  submitted_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_note (
  note_id STRING NOT NULL,
  entity_name STRING NOT NULL,
  entity_id STRING NOT NULL,
  note_type STRING NOT NULL,
  note_text STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_user_directory (
  user_id STRING NOT NULL,
  login_identifier STRING NOT NULL,
  email STRING,
  network_id STRING,
  first_name STRING,
  last_name STRING,
  display_name STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  last_seen_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_user_settings (
  setting_id STRING NOT NULL,
  user_principal STRING NOT NULL,
  setting_key STRING NOT NULL,
  setting_value_json STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_lookup_option (
  option_id STRING NOT NULL,
  lookup_type STRING NOT NULL,
  option_code STRING NOT NULL,
  option_label STRING NOT NULL,
  sort_order INT NOT NULL,
  active_flag BOOLEAN NOT NULL,
  valid_from_ts TIMESTAMP NOT NULL,
  valid_to_ts TIMESTAMP,
  is_current BOOLEAN NOT NULL,
  deleted_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_usage_log (
  usage_event_id STRING NOT NULL,
  user_principal STRING NOT NULL,
  page_name STRING NOT NULL,
  event_type STRING NOT NULL,
  event_ts TIMESTAMP NOT NULL,
  payload_json STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_project (
  project_id STRING NOT NULL,
  vendor_id STRING,
  project_name STRING NOT NULL,
  project_type STRING,
  status STRING NOT NULL,
  start_date DATE,
  target_date DATE,
  owner_principal STRING,
  description STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_project_vendor_map (
  project_vendor_map_id STRING NOT NULL,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_project_offering_map (
  project_offering_map_id STRING NOT NULL,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_project_demo (
  project_demo_id STRING NOT NULL,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  demo_name STRING NOT NULL,
  demo_datetime_start TIMESTAMP,
  demo_datetime_end TIMESTAMP,
  demo_type STRING,
  outcome STRING,
  score DOUBLE,
  attendees_internal STRING,
  attendees_vendor STRING,
  notes STRING,
  followups STRING,
  linked_offering_id STRING,
  linked_vendor_demo_id STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_project_note (
  project_note_id STRING NOT NULL,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  note_text STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_profile (
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  estimated_monthly_cost DOUBLE,
  implementation_notes STRING,
  data_sent STRING,
  data_received STRING,
  integration_method STRING,
  inbound_method STRING,
  inbound_landing_zone STRING,
  inbound_identifiers STRING,
  inbound_reporting_layer STRING,
  inbound_ingestion_notes STRING,
  outbound_method STRING,
  outbound_creation_process STRING,
  outbound_delivery_process STRING,
  outbound_responsible_owner STRING,
  outbound_notes STRING,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_data_flow (
  data_flow_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  direction STRING NOT NULL,
  flow_name STRING NOT NULL,
  method STRING,
  data_description STRING,
  endpoint_details STRING,
  identifiers STRING,
  reporting_layer STRING,
  creation_process STRING,
  delivery_process STRING,
  owner_user_principal STRING,
  notes STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_ticket (
  ticket_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  ticket_system STRING,
  external_ticket_id STRING,
  title STRING NOT NULL,
  status STRING NOT NULL,
  priority STRING,
  opened_date DATE,
  closed_date DATE,
  notes STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_invoice (
  invoice_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  invoice_number STRING,
  invoice_date DATE NOT NULL,
  amount DOUBLE NOT NULL,
  currency_code STRING NOT NULL,
  invoice_status STRING NOT NULL,
  notes STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_document_link (
  doc_id STRING NOT NULL,
  entity_type STRING NOT NULL,
  entity_id STRING NOT NULL,
  doc_title STRING NOT NULL,
  doc_url STRING NOT NULL,
  doc_type STRING NOT NULL,
  tags STRING,
  owner STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

-- Security tables
CREATE TABLE IF NOT EXISTS {fq_schema}.sec_user_role_map (
  user_principal STRING NOT NULL,
  role_code STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  granted_by STRING NOT NULL,
  granted_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.sec_group_role_map (
  group_principal STRING NOT NULL,
  role_code STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  granted_by STRING NOT NULL,
  granted_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.sec_user_org_scope (
  user_principal STRING NOT NULL,
  org_id STRING NOT NULL,
  scope_level STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  granted_at TIMESTAMP NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.sec_role_definition (
  role_code STRING NOT NULL,
  role_name STRING NOT NULL,
  description STRING,
  approval_level INT NOT NULL,
  can_edit BOOLEAN NOT NULL,
  can_report BOOLEAN NOT NULL,
  can_direct_apply BOOLEAN NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.sec_role_permission (
  role_code STRING NOT NULL,
  object_name STRING NOT NULL,
  action_code STRING NOT NULL,
  active_flag BOOLEAN NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA;

-- Backward-compatible column additions for older schemas.
ALTER TABLE {fq_schema}.core_vendor_offering
ADD COLUMN IF NOT EXISTS lob STRING;

ALTER TABLE {fq_schema}.core_vendor_offering
ADD COLUMN IF NOT EXISTS service_type STRING;

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

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS inbound_method STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS inbound_landing_zone STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS inbound_identifiers STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS inbound_reporting_layer STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS inbound_ingestion_notes STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS outbound_method STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS outbound_creation_process STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS outbound_delivery_process STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS outbound_responsible_owner STRING;

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMN IF NOT EXISTS outbound_notes STRING;

-- Normalize legacy login/principal string references to canonical app_user_directory.user_id values.
-- This is a no-op for new schemas and safe to re-run.
MERGE INTO {fq_schema}.core_vendor_business_owner t
USING {fq_schema}.app_user_directory u
ON lower(t.owner_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.owner_user_principal = u.user_id;

MERGE INTO {fq_schema}.core_offering_business_owner t
USING {fq_schema}.app_user_directory u
ON lower(t.owner_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.owner_user_principal = u.user_id;

MERGE INTO {fq_schema}.core_contract_event t
USING {fq_schema}.app_user_directory u
ON lower(t.actor_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.actor_user_principal = u.user_id;

MERGE INTO {fq_schema}.audit_entity_change t
USING {fq_schema}.app_user_directory u
ON lower(t.actor_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.actor_user_principal = u.user_id;

MERGE INTO {fq_schema}.audit_workflow_event t
USING {fq_schema}.app_user_directory u
ON lower(t.actor_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.actor_user_principal = u.user_id;

MERGE INTO {fq_schema}.audit_access_event t
USING {fq_schema}.app_user_directory u
ON lower(t.actor_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.actor_user_principal = u.user_id;

MERGE INTO {fq_schema}.audit_access_event t
USING {fq_schema}.app_user_directory u
ON lower(t.target_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.target_user_principal = u.user_id;

MERGE INTO {fq_schema}.app_onboarding_request t
USING {fq_schema}.app_user_directory u
ON lower(t.requestor_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.requestor_user_principal = u.user_id;

MERGE INTO {fq_schema}.app_vendor_change_request t
USING {fq_schema}.app_user_directory u
ON lower(t.requestor_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.requestor_user_principal = u.user_id;

MERGE INTO {fq_schema}.app_onboarding_approval t
USING {fq_schema}.app_user_directory u
ON lower(t.approver_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.approver_user_principal = u.user_id;

MERGE INTO {fq_schema}.app_access_request t
USING {fq_schema}.app_user_directory u
ON lower(t.requester_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.requester_user_principal = u.user_id;

MERGE INTO {fq_schema}.app_user_settings t
USING {fq_schema}.app_user_directory u
ON lower(t.user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.user_principal = u.user_id;

MERGE INTO {fq_schema}.app_usage_log t
USING {fq_schema}.app_user_directory u
ON lower(t.user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.user_principal = u.user_id;

MERGE INTO {fq_schema}.app_project t
USING {fq_schema}.app_user_directory u
ON lower(t.owner_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.owner_principal = u.user_id;

MERGE INTO {fq_schema}.app_offering_data_flow t
USING {fq_schema}.app_user_directory u
ON lower(t.owner_user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.owner_user_principal = u.user_id;

MERGE INTO {fq_schema}.sec_user_role_map t
USING {fq_schema}.app_user_directory u
ON lower(t.user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.user_principal = u.user_id;

MERGE INTO {fq_schema}.sec_user_role_map t
USING {fq_schema}.app_user_directory u
ON lower(t.granted_by) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.granted_by = u.user_id;

MERGE INTO {fq_schema}.sec_user_org_scope t
USING {fq_schema}.app_user_directory u
ON lower(t.user_principal) = lower(u.login_identifier)
WHEN MATCHED THEN UPDATE SET t.user_principal = u.user_id;

-- Reporting tables used by app analytics/reporting SQL.
CREATE TABLE IF NOT EXISTS {fq_schema}.rpt_spend_fact (
  spend_fact_id STRING,
  month DATE,
  org_id STRING,
  vendor_id STRING,
  category STRING,
  amount DOUBLE,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.rpt_contract_renewals (
  contract_id STRING,
  vendor_id STRING,
  contract_number STRING,
  contract_status STRING,
  end_date DATE,
  days_to_renewal BIGINT,
  annual_value DOUBLE,
  owner_org_id STRING
) USING DELTA;

CREATE OR REPLACE VIEW {fq_schema}.rpt_vendor_360 AS
SELECT
  vendor_id,
  legal_name,
  display_name,
  lifecycle_state,
  owner_org_id,
  risk_tier,
  updated_at
FROM {fq_schema}.core_vendor;

CREATE OR REPLACE VIEW {fq_schema}.rpt_vendor_demo_outcomes AS
SELECT
  demo_id,
  vendor_id,
  offering_id,
  demo_date,
  overall_score,
  selection_outcome,
  non_selection_reason_code,
  notes
FROM {fq_schema}.core_vendor_demo;

CREATE OR REPLACE VIEW {fq_schema}.rpt_contract_cancellations AS
SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  e.event_ts AS cancelled_at,
  e.reason_code,
  e.notes
FROM {fq_schema}.core_contract c
INNER JOIN {fq_schema}.core_contract_event e
  ON c.contract_id = e.contract_id
WHERE e.event_type = 'contract_cancelled';
