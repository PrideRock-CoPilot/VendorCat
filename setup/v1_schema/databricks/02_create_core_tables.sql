USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

CREATE TABLE IF NOT EXISTS vendor (
  vendor_id STRING,
  legal_name STRING,
  display_name STRING,
  lifecycle_state_id STRING,
  risk_tier_id STRING,
  primary_lob_id STRING,
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
  primary_lob_id STRING,
  primary_service_type_id STRING,
  criticality_tier STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  updated_by STRING
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
  primary_lob_id STRING,
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