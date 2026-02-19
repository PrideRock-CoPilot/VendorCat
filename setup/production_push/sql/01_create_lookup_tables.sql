USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

CREATE TABLE IF NOT EXISTS lkp_line_of_business (
  lob_id STRING,
  lob_code STRING,
  lob_name STRING,
  active_flag BOOLEAN,
  sort_order INT,
  effective_from TIMESTAMP,
  effective_to TIMESTAMP,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS lkp_service_type (
  service_type_id STRING,
  service_type_code STRING,
  service_type_name STRING,
  active_flag BOOLEAN,
  sort_order INT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS lkp_owner_role (
  owner_role_id STRING,
  owner_role_code STRING,
  owner_role_name STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS lkp_contact_type (
  contact_type_id STRING,
  contact_type_code STRING,
  contact_type_name STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS lkp_lifecycle_state (
  lifecycle_state_id STRING,
  lifecycle_state_code STRING,
  lifecycle_state_name STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS lkp_risk_tier (
  risk_tier_id STRING,
  risk_tier_code STRING,
  risk_tier_name STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) USING DELTA;