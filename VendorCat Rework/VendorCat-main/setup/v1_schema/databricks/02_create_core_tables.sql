USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

CREATE TABLE IF NOT EXISTS vendor (
  vendor_id STRING,
  legal_name STRING,
  display_name STRING,
  lifecycle_state_id STRING,
  risk_tier_id STRING,
  primary_business_unit_id STRING,
  primary_owner_organization_id STRING,
  vendor_category_id STRING,
  compliance_category_id STRING,
  gl_category_id STRING,
  delegated_vendor_flag BOOLEAN,
  health_care_vendor_flag BOOLEAN,
  source_system STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS offering (
  offering_id STRING,
  vendor_id STRING,
  offering_name STRING,
  lifecycle_state_id STRING,
  primary_business_unit_id STRING,
  primary_service_type_id STRING,
  criticality_tier STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS contract (
  contract_id STRING,
  vendor_id STRING,
  offering_id STRING,
  contract_number STRING,
  contract_status STRING,
  start_date STRING,
  end_date STRING,
  cancelled_flag BOOLEAN,
  annual_value DOUBLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS contract_event (
  contract_event_id STRING,
  contract_id STRING,
  event_type STRING,
  event_ts STRING,
  reason_code STRING,
  notes STRING,
  actor_user_principal STRING,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_demo (
  demo_id STRING,
  vendor_id STRING,
  offering_id STRING,
  demo_date STRING,
  overall_score DOUBLE,
  selection_outcome STRING,
  non_selection_reason_code STRING,
  notes STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_demo_score (
  demo_score_id STRING,
  demo_id STRING,
  score_category STRING,
  score_value DOUBLE,
  weight DOUBLE,
  comments STRING,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_demo_note (
  demo_note_id STRING,
  demo_id STRING,
  note_type STRING,
  note_text STRING,
  created_at TIMESTAMP,
  created_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_identifier (
  vendor_identifier_id STRING,
  vendor_id STRING,
  source_system_code STRING,
  source_vendor_key STRING,
  identifier_type STRING,
  is_primary_source BOOLEAN,
  verification_status STRING,
  active_flag BOOLEAN,
  first_seen_at TIMESTAMP,
  last_seen_at TIMESTAMP,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS project (
  project_id STRING,
  project_name STRING,
  lifecycle_state_id STRING,
  primary_business_unit_id STRING,
  target_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS project_offering_map (
  project_offering_map_id STRING,
  project_id STRING,
  offering_id STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  ended_at TIMESTAMP
) USING DELTA;
