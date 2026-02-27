-- VendorCatalog canonical schema (Phase 2 skeleton)

CREATE TABLE IF NOT EXISTS vc_user_directory (
  user_id VARCHAR PRIMARY KEY,
  user_principal VARCHAR NOT NULL UNIQUE,
  display_name VARCHAR NOT NULL,
  email VARCHAR,
  active_flag BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_role_definition (
  role_code VARCHAR PRIMARY KEY,
  role_name VARCHAR NOT NULL,
  active_flag BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS vc_user_role_map (
  user_role_map_id VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  role_code VARCHAR NOT NULL,
  active_flag BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_vendor (
  vendor_id VARCHAR PRIMARY KEY,
  legal_name VARCHAR NOT NULL,
  display_name VARCHAR NOT NULL,
  lifecycle_state VARCHAR NOT NULL,
  owner_org_id VARCHAR NOT NULL,
  risk_tier VARCHAR NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_offering (
  offering_id VARCHAR PRIMARY KEY,
  vendor_id VARCHAR NOT NULL,
  offering_name VARCHAR NOT NULL,
  offering_type VARCHAR,
  lob VARCHAR,
  service_type VARCHAR,
  lifecycle_state VARCHAR NOT NULL,
  criticality_tier VARCHAR,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_contract (
  contract_id VARCHAR PRIMARY KEY,
  vendor_id VARCHAR NOT NULL,
  offering_id VARCHAR,
  contract_number VARCHAR,
  contract_status VARCHAR NOT NULL,
  start_date DATE,
  end_date DATE,
  cancelled_flag BOOLEAN NOT NULL DEFAULT FALSE,
  annual_value DECIMAL(14, 2),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_project (
  project_id VARCHAR PRIMARY KEY,
  project_name VARCHAR NOT NULL,
  owner_principal VARCHAR NOT NULL,
  lifecycle_state VARCHAR NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_demo (
  demo_id VARCHAR PRIMARY KEY,
  demo_name VARCHAR NOT NULL,
  demo_type VARCHAR,
  demo_outcome VARCHAR,
  lifecycle_state VARCHAR NOT NULL,
  project_id VARCHAR,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_import_job (
  import_job_id VARCHAR PRIMARY KEY,
  source_system VARCHAR NOT NULL,
  source_object VARCHAR,
  file_name VARCHAR NOT NULL,
  file_format VARCHAR,
  status VARCHAR NOT NULL,
  submitted_by VARCHAR NOT NULL,
  mapping_profile_id VARCHAR,
  row_count INTEGER NOT NULL DEFAULT 0,
  staged_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_mapping_profile (
  profile_id VARCHAR PRIMARY KEY,
  profile_name VARCHAR NOT NULL,
  layout_key VARCHAR NOT NULL,
  file_format VARCHAR NOT NULL,
  source_fields_json TEXT,
  source_target_mapping_json TEXT,
  created_by VARCHAR NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_workflow_decision (
  decision_id VARCHAR PRIMARY KEY,
  workflow_name VARCHAR NOT NULL,
  submitted_by VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  action VARCHAR NOT NULL,
  context_json TEXT,
  reviewed_by VARCHAR,
  review_note TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vc_report_run (
  report_run_id VARCHAR PRIMARY KEY,
  report_type VARCHAR NOT NULL,
  report_name VARCHAR NOT NULL,
  report_format VARCHAR NOT NULL DEFAULT 'excel',
  status VARCHAR NOT NULL DEFAULT 'scheduled',
  triggered_by VARCHAR NOT NULL,
  scheduled_time TIMESTAMP NOT NULL,
  started_time TIMESTAMP,
  completed_time TIMESTAMP,
  row_count INTEGER NOT NULL DEFAULT 0,
  file_path VARCHAR,
  error_message TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vc_help_article (
  article_id VARCHAR PRIMARY KEY,
  article_title VARCHAR NOT NULL,
  category VARCHAR NOT NULL,
  content_markdown TEXT NOT NULL,
  is_published BOOLEAN NOT NULL DEFAULT FALSE,
  view_count INTEGER NOT NULL DEFAULT 0,
  author VARCHAR NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);