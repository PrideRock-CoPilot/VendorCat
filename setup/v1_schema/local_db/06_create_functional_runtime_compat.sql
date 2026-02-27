PRAGMA foreign_keys = ON;

-- Transitional runtime compatibility layer (Wave 1b).
-- These tables preserve existing application behavior during canonical V1 migration.

CREATE TABLE IF NOT EXISTS src_ingest_batch (
  batch_id TEXT PRIMARY KEY,
  source_system TEXT NOT NULL,
  source_object TEXT NOT NULL,
  extract_ts TEXT NOT NULL,
  loaded_ts TEXT NOT NULL,
  row_count INTEGER,
  status TEXT
);

CREATE TABLE IF NOT EXISTS src_peoplesoft_vendor_raw (
  batch_id TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_extract_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  PRIMARY KEY (batch_id, source_record_id, source_extract_ts),
  FOREIGN KEY (batch_id) REFERENCES src_ingest_batch(batch_id)
);

CREATE TABLE IF NOT EXISTS src_zycus_vendor_raw (
  batch_id TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_extract_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  PRIMARY KEY (batch_id, source_record_id, source_extract_ts),
  FOREIGN KEY (batch_id) REFERENCES src_ingest_batch(batch_id)
);

CREATE TABLE IF NOT EXISTS src_spreadsheet_vendor_raw (
  batch_id TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_extract_ts TEXT NOT NULL,
  file_name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  PRIMARY KEY (batch_id, source_record_id, source_extract_ts),
  FOREIGN KEY (batch_id) REFERENCES src_ingest_batch(batch_id)
);

CREATE TABLE IF NOT EXISTS core_vendor (
  vendor_id TEXT PRIMARY KEY,
  legal_name TEXT NOT NULL,
  display_name TEXT,
  lifecycle_state TEXT NOT NULL,
  owner_org_id TEXT NOT NULL,
  risk_tier TEXT,
  source_system TEXT,
  source_record_id TEXT,
  source_batch_id TEXT,
  source_extract_ts TEXT,
  merged_into_vendor_id TEXT,
  merged_at TEXT,
  merged_by TEXT,
  merge_reason TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS core_vendor_identifier (
  vendor_identifier_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  identifier_type TEXT NOT NULL,
  identifier_value TEXT NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
  country_code TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (vendor_id, identifier_type, identifier_value)
);

CREATE TABLE IF NOT EXISTS core_vendor_contact (
  vendor_contact_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  contact_type TEXT NOT NULL,
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS core_vendor_org_assignment (
  vendor_org_assignment_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  assignment_type TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS core_vendor_business_owner (
  vendor_owner_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  owner_user_principal TEXT NOT NULL,
  owner_role TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS core_vendor_offering (
  offering_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  offering_name TEXT NOT NULL,
  offering_type TEXT,
  lob TEXT,
  service_type TEXT,
  lifecycle_state TEXT NOT NULL,
  criticality_tier TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (vendor_id, offering_name)
);

CREATE TABLE IF NOT EXISTS core_offering_business_owner (
  offering_owner_id TEXT PRIMARY KEY,
  offering_id TEXT NOT NULL,
  owner_user_principal TEXT NOT NULL,
  owner_role TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id)
);

CREATE TABLE IF NOT EXISTS core_offering_contact (
  offering_contact_id TEXT PRIMARY KEY,
  offering_id TEXT NOT NULL,
  contact_type TEXT NOT NULL,
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id)
);

CREATE TABLE IF NOT EXISTS core_contract (
  contract_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  offering_id TEXT,
  contract_number TEXT,
  contract_status TEXT NOT NULL,
  start_date TEXT,
  end_date TEXT,
  cancelled_flag INTEGER NOT NULL DEFAULT 0 CHECK (cancelled_flag IN (0, 1)),
  annual_value REAL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id)
);

CREATE TABLE IF NOT EXISTS core_contract_event (
  contract_event_id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  reason_code TEXT,
  notes TEXT,
  actor_user_principal TEXT NOT NULL,
  FOREIGN KEY (contract_id) REFERENCES core_contract(contract_id)
);

CREATE TABLE IF NOT EXISTS core_vendor_demo (
  demo_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  offering_id TEXT,
  demo_date TEXT NOT NULL,
  overall_score REAL,
  selection_outcome TEXT NOT NULL,
  non_selection_reason_code TEXT,
  notes TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id)
);

CREATE TABLE IF NOT EXISTS core_vendor_demo_score (
  demo_score_id TEXT PRIMARY KEY,
  demo_id TEXT NOT NULL,
  score_category TEXT NOT NULL,
  score_value REAL NOT NULL,
  weight REAL,
  comments TEXT,
  FOREIGN KEY (demo_id) REFERENCES core_vendor_demo(demo_id)
);

CREATE TABLE IF NOT EXISTS core_vendor_demo_note (
  demo_note_id TEXT PRIMARY KEY,
  demo_id TEXT NOT NULL,
  note_type TEXT NOT NULL,
  note_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  FOREIGN KEY (demo_id) REFERENCES core_vendor_demo(demo_id)
);

CREATE TABLE IF NOT EXISTS hist_vendor (
  vendor_hist_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  valid_from_ts TEXT NOT NULL,
  valid_to_ts TEXT,
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  change_reason TEXT,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (vendor_id, version_no)
);

CREATE TABLE IF NOT EXISTS hist_vendor_offering (
  vendor_offering_hist_id TEXT PRIMARY KEY,
  offering_id TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  valid_from_ts TEXT NOT NULL,
  valid_to_ts TEXT,
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  change_reason TEXT,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  UNIQUE (offering_id, version_no)
);

CREATE TABLE IF NOT EXISTS hist_contract (
  contract_hist_id TEXT PRIMARY KEY,
  contract_id TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  valid_from_ts TEXT NOT NULL,
  valid_to_ts TEXT,
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  change_reason TEXT,
  FOREIGN KEY (contract_id) REFERENCES core_contract(contract_id),
  UNIQUE (contract_id, version_no)
);

CREATE TABLE IF NOT EXISTS app_onboarding_request (
  request_id TEXT PRIMARY KEY,
  requestor_user_principal TEXT NOT NULL,
  vendor_name_raw TEXT NOT NULL,
  priority TEXT,
  status TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_vendor_change_request (
  change_request_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  requestor_user_principal TEXT NOT NULL,
  change_type TEXT NOT NULL,
  requested_payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS app_onboarding_task (
  task_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  assignee_group TEXT,
  due_at TEXT,
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (request_id) REFERENCES app_onboarding_request(request_id)
);

CREATE TABLE IF NOT EXISTS app_onboarding_approval (
  approval_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  stage_name TEXT NOT NULL,
  approver_user_principal TEXT,
  decision TEXT,
  decided_at TEXT,
  comments TEXT,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (request_id) REFERENCES app_onboarding_request(request_id)
);

CREATE TABLE IF NOT EXISTS app_access_request (
  access_request_id TEXT PRIMARY KEY,
  requester_user_principal TEXT NOT NULL,
  requested_role TEXT NOT NULL,
  justification TEXT,
  status TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (requested_role) REFERENCES sec_role_definition(role_code)
);

CREATE TABLE IF NOT EXISTS app_note (
  note_id TEXT PRIMARY KEY,
  entity_name TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  note_type TEXT NOT NULL,
  note_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_vendor_warning (
  warning_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  warning_category TEXT NOT NULL,
  severity TEXT NOT NULL,
  warning_status TEXT NOT NULL,
  warning_title TEXT NOT NULL,
  warning_detail TEXT,
  source_table TEXT,
  source_version TEXT,
  file_name TEXT,
  detected_at TEXT,
  resolved_at TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS app_employee_directory (
  login_identifier TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  network_id TEXT,
  employee_id TEXT,
  manager_id TEXT,
  first_name TEXT,
  last_name TEXT,
  display_name TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1))
);

CREATE TABLE IF NOT EXISTS app_lookup_option (
  option_id TEXT PRIMARY KEY,
  lookup_type TEXT NOT NULL,
  option_code TEXT NOT NULL,
  option_label TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 100,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  valid_from_ts TEXT NOT NULL,
  valid_to_ts TEXT,
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  deleted_flag INTEGER NOT NULL DEFAULT 0 CHECK (deleted_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  UNIQUE (lookup_type, option_code, is_current)
);

CREATE TABLE IF NOT EXISTS app_project (
  project_id TEXT PRIMARY KEY,
  vendor_id TEXT,
  project_name TEXT NOT NULL,
  project_type TEXT,
  status TEXT NOT NULL,
  start_date TEXT,
  target_date TEXT,
  owner_principal TEXT,
  description TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS app_project_vendor_map (
  project_vendor_map_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES app_project(project_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (project_id, vendor_id, active_flag)
);

CREATE TABLE IF NOT EXISTS app_project_offering_map (
  project_offering_map_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  offering_id TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES app_project(project_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  UNIQUE (project_id, offering_id, active_flag)
);

CREATE TABLE IF NOT EXISTS app_project_demo (
  project_demo_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  demo_name TEXT NOT NULL,
  demo_datetime_start TEXT,
  demo_datetime_end TEXT,
  demo_type TEXT,
  outcome TEXT,
  score REAL,
  attendees_internal TEXT,
  attendees_vendor TEXT,
  notes TEXT,
  followups TEXT,
  linked_offering_id TEXT,
  linked_vendor_demo_id TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES app_project(project_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  FOREIGN KEY (linked_offering_id) REFERENCES core_vendor_offering(offering_id),
  FOREIGN KEY (linked_vendor_demo_id) REFERENCES core_vendor_demo(demo_id)
);

CREATE TABLE IF NOT EXISTS app_project_note (
  project_note_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  note_text TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES app_project(project_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS app_offering_profile (
  offering_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  estimated_monthly_cost REAL,
  implementation_notes TEXT,
  data_sent TEXT,
  data_received TEXT,
  integration_method TEXT,
  inbound_method TEXT,
  inbound_landing_zone TEXT,
  inbound_identifiers TEXT,
  inbound_reporting_layer TEXT,
  inbound_ingestion_notes TEXT,
  outbound_method TEXT,
  outbound_creation_process TEXT,
  outbound_delivery_process TEXT,
  outbound_responsible_owner TEXT,
  outbound_notes TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
);

CREATE TABLE IF NOT EXISTS app_offering_data_flow (
  data_flow_id TEXT PRIMARY KEY,
  offering_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  flow_name TEXT NOT NULL,
  method TEXT,
  data_description TEXT,
  endpoint_details TEXT,
  identifiers TEXT,
  reporting_layer TEXT,
  creation_process TEXT,
  delivery_process TEXT,
  owner_user_principal TEXT,
  notes TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (offering_id, flow_name, direction, active_flag)
);

CREATE TABLE IF NOT EXISTS app_offering_ticket (
  ticket_id TEXT PRIMARY KEY,
  offering_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  ticket_system TEXT,
  external_ticket_id TEXT,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT,
  opened_date TEXT,
  closed_date TEXT,
  notes TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (offering_id, ticket_system, external_ticket_id)
);

CREATE TABLE IF NOT EXISTS app_offering_invoice (
  invoice_id TEXT PRIMARY KEY,
  offering_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  invoice_number TEXT,
  invoice_date TEXT NOT NULL,
  amount REAL NOT NULL,
  currency_code TEXT NOT NULL,
  invoice_status TEXT NOT NULL,
  notes TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (offering_id, invoice_number, invoice_date)
);

CREATE TABLE IF NOT EXISTS app_offering_payment (
  payment_id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL,
  offering_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  payment_reference TEXT,
  payment_date TEXT NOT NULL,
  amount REAL NOT NULL,
  currency_code TEXT NOT NULL,
  payment_status TEXT NOT NULL,
  notes TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (invoice_id) REFERENCES app_offering_invoice(invoice_id),
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id),
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id),
  UNIQUE (invoice_id, payment_reference, payment_date)
);

CREATE TABLE IF NOT EXISTS app_document_link (
  doc_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  doc_title TEXT NOT NULL,
  doc_url TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  tags TEXT,
  owner TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  UNIQUE (entity_type, entity_id, doc_url, active_flag)
);

CREATE TABLE IF NOT EXISTS app_import_job (
  import_job_id TEXT PRIMARY KEY,
  layout_key TEXT NOT NULL,
  source_system TEXT NOT NULL,
  source_object TEXT,
  file_name TEXT,
  file_type TEXT,
  detected_format TEXT,
  parser_config_json TEXT,
  mapping_profile_id TEXT,
  mapping_request_id TEXT,
  context_json TEXT,
  row_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_count INTEGER NOT NULL DEFAULT 0,
  merged_count INTEGER NOT NULL DEFAULT 0,
  skipped_count INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  applied_at TEXT,
  applied_by TEXT
);

CREATE TABLE IF NOT EXISTS app_import_stage_row (
  import_stage_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_key TEXT,
  source_group_key TEXT,
  row_payload_json TEXT NOT NULL,
  suggested_action TEXT,
  suggested_target_id TEXT,
  decision_action TEXT,
  decision_target_id TEXT,
  decision_payload_json TEXT,
  decision_updated_at TEXT,
  decision_updated_by TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id),
  UNIQUE (import_job_id, row_index)
);

CREATE TABLE IF NOT EXISTS app_import_review_area_state (
  import_review_area_state_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  area_key TEXT NOT NULL,
  area_order INTEGER NOT NULL,
  status TEXT NOT NULL,
  confirmed_at TEXT,
  confirmed_by TEXT,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id),
  UNIQUE (import_job_id, area_key)
);

CREATE TABLE IF NOT EXISTS app_import_stage_vendor (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_identifier (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_contact (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_vendor_owner (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_offering (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_offering_owner (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_offering_contact (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_contract (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_project (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_invoice (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_stage_payment (
  import_stage_area_row_id TEXT PRIMARY KEY,
  import_job_id TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  line_number TEXT,
  area_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id)
);

CREATE TABLE IF NOT EXISTS app_import_mapping_profile (
  profile_id TEXT PRIMARY KEY,
  layout_key TEXT NOT NULL,
  profile_name TEXT NOT NULL,
  file_format TEXT,
  source_signature TEXT,
  source_fields_json TEXT,
  source_target_mapping_json TEXT,
  field_mapping_json TEXT,
  parser_options_json TEXT,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_import_mapping_profile_request (
  profile_request_id TEXT PRIMARY KEY,
  import_job_id TEXT,
  submitted_by TEXT NOT NULL,
  layout_key TEXT NOT NULL,
  proposed_profile_name TEXT,
  file_format TEXT,
  source_system TEXT,
  source_object TEXT,
  source_signature TEXT,
  source_fields_json TEXT,
  source_target_mapping_json TEXT,
  parser_options_json TEXT,
  sample_rows_json TEXT,
  status TEXT NOT NULL,
  review_note TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  approved_profile_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (import_job_id) REFERENCES app_import_job(import_job_id),
  FOREIGN KEY (approved_profile_id) REFERENCES app_import_mapping_profile(profile_id)
);
