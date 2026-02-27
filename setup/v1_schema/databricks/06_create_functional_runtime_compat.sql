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
  merged_into_vendor_id STRING,
  merged_at STRING,
  merged_by STRING,
  merge_reason STRING,
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

CREATE TABLE IF NOT EXISTS app_vendor_warning (
  warning_id STRING,
  vendor_id STRING NOT NULL,
  warning_category STRING NOT NULL,
  severity STRING NOT NULL,
  warning_status STRING NOT NULL,
  warning_title STRING NOT NULL,
  warning_detail STRING,
  source_table STRING,
  source_version STRING,
  file_name STRING,
  detected_at STRING,
  resolved_at STRING,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  updated_at STRING NOT NULL,
  updated_by STRING NOT NULL
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

CREATE TABLE IF NOT EXISTS app_offering_payment (
  payment_id STRING,
  invoice_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  payment_reference STRING,
  payment_date STRING NOT NULL,
  amount DOUBLE NOT NULL,
  currency_code STRING NOT NULL,
  payment_status STRING NOT NULL,
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

CREATE TABLE IF NOT EXISTS app_import_job (
  import_job_id STRING,
  layout_key STRING NOT NULL,
  source_system STRING NOT NULL,
  source_object STRING,
  file_name STRING,
  file_type STRING,
  detected_format STRING,
  parser_config_json STRING,
  mapping_profile_id STRING,
  mapping_request_id STRING,
  context_json STRING,
  row_count INT NOT NULL,
  status STRING NOT NULL,
  created_count INT NOT NULL,
  merged_count INT NOT NULL,
  skipped_count INT NOT NULL,
  failed_count INT NOT NULL,
  error_message STRING,
  created_at STRING NOT NULL,
  created_by STRING NOT NULL,
  applied_at STRING,
  applied_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_row (
  import_stage_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_key STRING,
  source_group_key STRING,
  row_payload_json STRING NOT NULL,
  suggested_action STRING,
  suggested_target_id STRING,
  decision_action STRING,
  decision_target_id STRING,
  decision_payload_json STRING,
  decision_updated_at STRING,
  decision_updated_by STRING,
  created_at STRING NOT NULL
) USING DELTA;

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

CREATE TABLE IF NOT EXISTS app_import_stage_vendor (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_identifier (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_contact (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_owner (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_offering (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_offering_owner (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_offering_contact (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_contract (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_project (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_invoice (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS app_import_stage_payment (
  import_stage_area_row_id STRING,
  import_job_id STRING NOT NULL,
  row_index INT NOT NULL,
  line_number STRING,
  area_payload_json STRING NOT NULL,
  created_at STRING NOT NULL
) USING DELTA;

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
