USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

-- Transitional runtime compatibility layer (Wave 1b).
-- Databricks counterpart of local runtime parity tables.

-- Transitional runtime compatibility layer (Wave 1b).
-- These tables preserve existing application behavior during canonical V1 migration.

CREATE TABLE IF NOT EXISTS src_ingest_batch (
  batch_id STRING,
  source_system STRING NOT NULL,
  source_object STRING NOT NULL,
  extract_ts STRING NOT NULL,
  loaded_ts STRING NOT NULL,
  row_count INT,
  status STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS src_peoplesoft_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts STRING NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS src_zycus_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts STRING NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS src_spreadsheet_vendor_raw (
  batch_id STRING NOT NULL,
  source_record_id STRING NOT NULL,
  source_extract_ts STRING NOT NULL,
  file_name STRING NOT NULL,
  payload_json STRING NOT NULL,
  ingested_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor (
  vendor_id STRING,
  legal_name STRING NOT NULL,
  display_name STRING,
  lifecycle_state STRING NOT NULL,
  owner_org_id STRING NOT NULL,
  risk_tier STRING,
  source_system STRING,
  source_record_id STRING,
  source_batch_id STRING,
  source_extract_ts STRING,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_identifier (
  vendor_identifier_id STRING,
  vendor_id STRING NOT NULL,
  identifier_type STRING NOT NULL,
  identifier_value STRING NOT NULL,
  is_primary INT NOT NULL DEFAULT 0,
  country_code STRING,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_contact (
  vendor_contact_id STRING,
  vendor_id STRING NOT NULL,
  contact_type STRING NOT NULL,
  full_name STRING NOT NULL,
  email STRING,
  phone STRING,
  active_flag INT NOT NULL DEFAULT 1,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_org_assignment (
  vendor_org_assignment_id STRING,
  vendor_id STRING NOT NULL,
  org_id STRING NOT NULL,
  assignment_type STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_business_owner (
  vendor_owner_id STRING,
  vendor_id STRING NOT NULL,
  owner_user_principal STRING NOT NULL,
  owner_role STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_offering (
  offering_id STRING,
  vendor_id STRING NOT NULL,
  offering_name STRING NOT NULL,
  offering_type STRING,
  lob STRING,
  service_type STRING,
  lifecycle_state STRING NOT NULL,
  criticality_tier STRING,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_offering_business_owner (
  offering_owner_id STRING,
  offering_id STRING NOT NULL,
  owner_user_principal STRING NOT NULL,
  owner_role STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_offering_contact (
  offering_contact_id STRING,
  offering_id STRING NOT NULL,
  contact_type STRING NOT NULL,
  full_name STRING NOT NULL,
  email STRING,
  phone STRING,
  active_flag INT NOT NULL DEFAULT 1,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_contract (
  contract_id STRING,
  vendor_id STRING NOT NULL,
  offering_id STRING,
  contract_number STRING,
  contract_status STRING NOT NULL,
  start_date STRING,
  end_date STRING,
  cancelled_flag INT NOT NULL DEFAULT 0,
  annual_value DOUBLE,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_contract_event (
  contract_event_id STRING,
  contract_id STRING NOT NULL,
  event_type STRING NOT NULL,
  event_ts STRING NOT NULL,
  reason_code STRING,
  notes STRING,
  actor_user_principal STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_demo (
  demo_id STRING,
  vendor_id STRING NOT NULL,
  offering_id STRING,
  demo_date STRING NOT NULL,
  overall_score DOUBLE,
  selection_outcome STRING NOT NULL,
  non_selection_reason_code STRING,
  notes STRING,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_demo_score (
  demo_score_id STRING,
  demo_id STRING NOT NULL,
  score_category STRING NOT NULL,
  score_value DOUBLE NOT NULL,
  weight DOUBLE,
  comments STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS core_vendor_demo_note (
  demo_note_id STRING,
  demo_id STRING NOT NULL,
  note_type STRING NOT NULL,
  note_text STRING NOT NULL,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS hist_vendor (
  vendor_hist_id STRING,
  vendor_id STRING NOT NULL,
  version_no INT NOT NULL,
  valid_from_ts STRING NOT NULL,
  valid_to_ts STRING,
  is_current INT NOT NULL DEFAULT 1,
  snapshot_json STRING NOT NULL,
  changed_by STRING NOT NULL,
  change_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS hist_vendor_offering (
  vendor_offering_hist_id STRING,
  offering_id STRING NOT NULL,
  version_no INT NOT NULL,
  valid_from_ts STRING NOT NULL,
  valid_to_ts STRING,
  is_current INT NOT NULL DEFAULT 1,
  snapshot_json STRING NOT NULL,
  changed_by STRING NOT NULL,
  change_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS hist_contract (
  contract_hist_id STRING,
  contract_id STRING NOT NULL,
  version_no INT NOT NULL,
  valid_from_ts STRING NOT NULL,
  valid_to_ts STRING,
  is_current INT NOT NULL DEFAULT 1,
  snapshot_json STRING NOT NULL,
  changed_by STRING NOT NULL,
  change_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_onboarding_request (
  request_id STRING,
  requestor_user_principal STRING NOT NULL,
  vendor_name_raw STRING NOT NULL,
  priority STRING,
  status STRING NOT NULL,
  submitted_at STRING NOT NULL,
  updated_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_vendor_change_request (
  change_request_id STRING,
  vendor_id STRING NOT NULL,
  requestor_user_principal STRING NOT NULL,
  change_type STRING NOT NULL,
  requested_payload_json STRING NOT NULL,
  status STRING NOT NULL,
  submitted_at STRING NOT NULL,
  updated_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_onboarding_task (
  task_id STRING,
  request_id STRING NOT NULL,
  task_type STRING NOT NULL,
  assignee_group STRING,
  due_at STRING,
  status STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_onboarding_approval (
  approval_id STRING,
  request_id STRING NOT NULL,
  stage_name STRING NOT NULL,
  approver_user_principal STRING,
  decision STRING,
  decided_at STRING,
  comments STRING,
  updated_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_access_request (
  access_request_id STRING,
  requester_user_principal STRING NOT NULL,
  requested_role STRING NOT NULL,
  justification STRING,
  status STRING NOT NULL,
  submitted_at STRING NOT NULL,
  updated_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_note (
  note_id STRING,
  entity_name STRING NOT NULL,
  entity_id STRING NOT NULL,
  note_type STRING NOT NULL,
  note_text STRING NOT NULL,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_employee_directory (
  login_identifier STRING,
  email STRING NOT NULL,
  network_id STRING,
  employee_id STRING,
  manager_id STRING,
  first_name STRING,
  last_name STRING,
  display_name STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_lookup_option (
  option_id STRING,
  lookup_type STRING NOT NULL,
  option_code STRING NOT NULL,
  option_label STRING NOT NULL,
  sort_order INT NOT NULL DEFAULT 100,
  active_flag INT NOT NULL DEFAULT 1,
  valid_from_ts STRING NOT NULL,
  valid_to_ts STRING,
  is_current INT NOT NULL DEFAULT 1,
  deleted_flag INT NOT NULL DEFAULT 0,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_project (
  project_id STRING,
  vendor_id STRING,
  project_name STRING NOT NULL,
  project_type STRING,
  status STRING NOT NULL,
  start_date STRING,
  target_date STRING,
  owner_principal STRING,
  description STRING,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_project_vendor_map (
  project_vendor_map_id STRING,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_project_offering_map (
  project_offering_map_id STRING,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_project_demo (
  project_demo_id STRING,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  demo_name STRING NOT NULL,
  demo_datetime_start STRING,
  demo_datetime_end STRING,
  demo_type STRING,
  outcome STRING,
  score DOUBLE,
  attendees_internal STRING,
  attendees_vendor STRING,
  notes STRING,
  followups STRING,
  linked_offering_id STRING,
  linked_vendor_demo_id STRING,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_project_note (
  project_note_id STRING,
  project_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  note_text STRING NOT NULL,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_offering_profile (
  offering_id STRING,
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
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_offering_data_flow (
  data_flow_id STRING,
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
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_offering_ticket (
  ticket_id STRING,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  ticket_system STRING,
  external_ticket_id STRING,
  title STRING NOT NULL,
  status STRING NOT NULL,
  priority STRING,
  opened_date STRING,
  closed_date STRING,
  notes STRING,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_offering_invoice (
  invoice_id STRING,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  invoice_number STRING,
  invoice_date STRING NOT NULL,
  amount DOUBLE NOT NULL,
  currency_code STRING NOT NULL,
  invoice_status STRING NOT NULL,
  notes STRING,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_document_link (
  doc_id STRING,
  entity_type STRING NOT NULL,
  entity_id STRING NOT NULL,
  doc_title STRING NOT NULL,
  doc_url STRING NOT NULL,
  doc_type STRING NOT NULL,
  tags STRING,
  owner STRING,
  active_flag INT NOT NULL DEFAULT 1,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;