PRAGMA foreign_keys = ON;

-- Source immutable tables
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
  ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS src_zycus_vendor_raw (
  batch_id TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_extract_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS src_spreadsheet_vendor_raw (
  batch_id TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  source_extract_ts TEXT NOT NULL,
  file_name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  ingested_at TEXT NOT NULL
);

-- Canonical current-state tables
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
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
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
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
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

-- History and audit
CREATE TABLE IF NOT EXISTS hist_vendor (
  vendor_hist_id TEXT PRIMARY KEY,
  vendor_id TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  valid_from_ts TEXT NOT NULL,
  valid_to_ts TEXT,
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  change_reason TEXT
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
  change_reason TEXT
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
  change_reason TEXT
);

CREATE TABLE IF NOT EXISTS audit_entity_change (
  change_event_id TEXT PRIMARY KEY,
  entity_name TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  actor_user_principal TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  request_id TEXT
);

CREATE TABLE IF NOT EXISTS audit_workflow_event (
  workflow_event_id TEXT PRIMARY KEY,
  workflow_type TEXT NOT NULL,
  workflow_id TEXT NOT NULL,
  old_status TEXT,
  new_status TEXT,
  actor_user_principal TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS audit_access_event (
  access_event_id TEXT PRIMARY KEY,
  actor_user_principal TEXT NOT NULL,
  action_type TEXT NOT NULL,
  target_user_principal TEXT,
  target_role TEXT,
  event_ts TEXT NOT NULL,
  notes TEXT
);

-- App workflow tables
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
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_onboarding_task (
  task_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  assignee_group TEXT,
  due_at TEXT,
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_onboarding_approval (
  approval_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  stage_name TEXT NOT NULL,
  approver_user_principal TEXT,
  decision TEXT,
  decided_at TEXT,
  comments TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_access_request (
  access_request_id TEXT PRIMARY KEY,
  requester_user_principal TEXT NOT NULL,
  requested_role TEXT NOT NULL,
  justification TEXT,
  status TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS app_user_directory (
  user_id TEXT PRIMARY KEY,
  login_identifier TEXT NOT NULL UNIQUE,
  email TEXT,
  network_id TEXT,
  employee_id TEXT,
  manager_id TEXT,
  first_name TEXT,
  last_name TEXT,
  display_name TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS app_user_settings (
  setting_id TEXT PRIMARY KEY,
  user_principal TEXT NOT NULL,
  setting_key TEXT NOT NULL,
  setting_value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
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
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_usage_log (
  usage_event_id TEXT PRIMARY KEY,
  user_principal TEXT NOT NULL,
  page_name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
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
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
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
  FOREIGN KEY (offering_id) REFERENCES core_vendor_offering(offering_id)
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
  FOREIGN KEY (linked_offering_id) REFERENCES core_vendor_offering(offering_id)
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
  FOREIGN KEY (project_id) REFERENCES app_project(project_id)
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
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
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
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
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
  FOREIGN KEY (vendor_id) REFERENCES core_vendor(vendor_id)
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
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_help_article (
  article_id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  section TEXT NOT NULL,
  article_type TEXT NOT NULL,
  role_visibility TEXT NOT NULL,
  content_md TEXT NOT NULL,
  owned_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_help_feedback (
  feedback_id TEXT PRIMARY KEY,
  article_id TEXT,
  article_slug TEXT,
  was_helpful INTEGER NOT NULL DEFAULT 0 CHECK (was_helpful IN (0, 1)),
  comment TEXT,
  user_principal TEXT,
  page_path TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_help_issue (
  issue_id TEXT PRIMARY KEY,
  article_id TEXT,
  article_slug TEXT,
  issue_title TEXT NOT NULL,
  issue_description TEXT NOT NULL,
  page_path TEXT,
  user_principal TEXT,
  created_at TEXT NOT NULL
);

-- Security tables
CREATE TABLE IF NOT EXISTS sec_user_role_map (
  user_principal TEXT NOT NULL,
  role_code TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  granted_by TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS sec_group_role_map (
  group_principal TEXT NOT NULL,
  role_code TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  granted_by TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS sec_user_org_scope (
  user_principal TEXT NOT NULL,
  org_id TEXT NOT NULL,
  scope_level TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  granted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sec_role_definition (
  role_code TEXT PRIMARY KEY,
  role_name TEXT NOT NULL,
  description TEXT,
  approval_level INTEGER NOT NULL DEFAULT 0,
  can_edit INTEGER NOT NULL DEFAULT 0 CHECK (can_edit IN (0, 1)),
  can_report INTEGER NOT NULL DEFAULT 0 CHECK (can_report IN (0, 1)),
  can_direct_apply INTEGER NOT NULL DEFAULT 0 CHECK (can_direct_apply IN (0, 1)),
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sec_role_permission (
  role_code TEXT NOT NULL,
  object_name TEXT NOT NULL,
  action_code TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL
);

-- Reporting views (local/dev unsecured variants)
CREATE VIEW IF NOT EXISTS rpt_spend_fact AS
SELECT
  date(i.invoice_date, 'start of month') AS month,
  i.vendor_id AS vendor_id,
  coalesce(v.owner_org_id, 'unknown') AS org_id,
  coalesce(o.offering_type, 'unknown') AS category,
  coalesce(i.amount, 0.0) AS amount
FROM app_offering_invoice i
INNER JOIN core_vendor v
  ON i.vendor_id = v.vendor_id
LEFT JOIN core_vendor_offering o
  ON i.offering_id = o.offering_id
WHERE coalesce(i.active_flag, 1) = 1
  AND lower(coalesce(i.invoice_status, '')) NOT IN ('cancelled', 'canceled', 'void', 'rejected');

CREATE VIEW IF NOT EXISTS rpt_contract_renewals AS
SELECT
  c.contract_id AS contract_id,
  c.vendor_id AS vendor_id,
  coalesce(v.display_name, v.legal_name, c.vendor_id) AS vendor_name,
  coalesce(v.owner_org_id, 'unknown') AS org_id,
  coalesce(o.offering_type, 'vendor_contract') AS category,
  c.end_date AS renewal_date,
  coalesce(c.annual_value, 0.0) AS annual_value,
  coalesce(v.risk_tier, 'unknown') AS risk_tier,
  CASE
    WHEN coalesce(c.cancelled_flag, 0) = 1 THEN 'cancelled'
    WHEN lower(coalesce(c.contract_status, '')) IN ('expired', 'terminated') THEN 'expired'
    WHEN lower(coalesce(c.contract_status, '')) IN ('pending_renewal', 'renewal_due') THEN 'pending_renewal'
    ELSE 'active'
  END AS renewal_status
FROM core_contract c
LEFT JOIN core_vendor v
  ON c.vendor_id = v.vendor_id
LEFT JOIN core_vendor_offering o
  ON c.offering_id = o.offering_id
WHERE c.end_date IS NOT NULL;

CREATE VIEW IF NOT EXISTS rpt_vendor_360 AS
SELECT
  vendor_id,
  legal_name,
  display_name,
  lifecycle_state,
  owner_org_id,
  risk_tier,
  updated_at
FROM core_vendor;

CREATE VIEW IF NOT EXISTS rpt_vendor_demo_outcomes AS
SELECT
  demo_id,
  vendor_id,
  offering_id,
  demo_date,
  overall_score,
  selection_outcome,
  non_selection_reason_code,
  notes
FROM core_vendor_demo;

CREATE VIEW IF NOT EXISTS rpt_contract_cancellations AS
SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  e.event_ts AS cancelled_at,
  e.reason_code,
  e.notes
FROM core_contract c
INNER JOIN core_contract_event e
  ON c.contract_id = e.contract_id
WHERE e.event_type = 'contract_cancelled';

CREATE VIEW IF NOT EXISTS vw_employee_directory AS
SELECT
  login_identifier,
  email,
  network_id,
  employee_id,
  manager_id,
  first_name,
  last_name,
  display_name,
  active_flag
FROM app_employee_directory;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_core_vendor_owner_org ON core_vendor(owner_org_id);
CREATE INDEX IF NOT EXISTS idx_core_vendor_display ON core_vendor(display_name);
CREATE INDEX IF NOT EXISTS idx_core_offering_vendor ON core_vendor_offering(vendor_id);
CREATE INDEX IF NOT EXISTS idx_core_contract_vendor ON core_contract(vendor_id);
CREATE INDEX IF NOT EXISTS idx_core_contract_offering ON core_contract(offering_id);
CREATE INDEX IF NOT EXISTS idx_core_demo_vendor ON core_vendor_demo(vendor_id);
CREATE INDEX IF NOT EXISTS idx_core_demo_offering ON core_vendor_demo(offering_id);
CREATE INDEX IF NOT EXISTS idx_app_project_vendor ON app_project(vendor_id);
CREATE INDEX IF NOT EXISTS idx_app_project_vendor_map_vendor ON app_project_vendor_map(vendor_id);
CREATE INDEX IF NOT EXISTS idx_app_project_vendor_map_project ON app_project_vendor_map(project_id);
CREATE INDEX IF NOT EXISTS idx_app_project_status ON app_project(status);
CREATE INDEX IF NOT EXISTS idx_app_project_demo_project ON app_project_demo(project_id);
CREATE INDEX IF NOT EXISTS idx_app_project_note_project ON app_project_note(project_id);
CREATE INDEX IF NOT EXISTS idx_app_offering_profile_vendor ON app_offering_profile(vendor_id);
CREATE INDEX IF NOT EXISTS idx_app_offering_data_flow_offering ON app_offering_data_flow(offering_id, active_flag, direction);
CREATE INDEX IF NOT EXISTS idx_app_offering_data_flow_vendor ON app_offering_data_flow(vendor_id, active_flag, direction);
CREATE INDEX IF NOT EXISTS idx_app_offering_ticket_offering ON app_offering_ticket(offering_id, active_flag, opened_date);
CREATE INDEX IF NOT EXISTS idx_app_offering_ticket_vendor ON app_offering_ticket(vendor_id, active_flag);
CREATE INDEX IF NOT EXISTS idx_app_offering_invoice_offering ON app_offering_invoice(offering_id, active_flag, invoice_date);
CREATE INDEX IF NOT EXISTS idx_app_offering_invoice_vendor ON app_offering_invoice(vendor_id, active_flag, invoice_date);
CREATE INDEX IF NOT EXISTS idx_app_doc_entity ON app_document_link(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_app_user_directory_login ON app_user_directory(login_identifier);
CREATE INDEX IF NOT EXISTS idx_app_user_directory_employee ON app_user_directory(employee_id);
CREATE INDEX IF NOT EXISTS idx_app_employee_directory_email ON app_employee_directory(email);
CREATE INDEX IF NOT EXISTS idx_app_employee_directory_network ON app_employee_directory(network_id);
CREATE INDEX IF NOT EXISTS idx_app_employee_directory_employee ON app_employee_directory(employee_id);
CREATE INDEX IF NOT EXISTS idx_app_lookup_type_code ON app_lookup_option(lookup_type, option_code);
CREATE INDEX IF NOT EXISTS idx_app_lookup_type_sort ON app_lookup_option(lookup_type, active_flag, sort_order);
CREATE INDEX IF NOT EXISTS idx_app_lookup_type_current ON app_lookup_option(lookup_type, is_current, sort_order);
CREATE INDEX IF NOT EXISTS idx_app_lookup_type_deleted ON app_lookup_option(lookup_type, deleted_flag, sort_order);
CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON app_usage_log(user_principal, event_ts);
CREATE INDEX IF NOT EXISTS idx_change_req_vendor ON app_vendor_change_request(vendor_id);
