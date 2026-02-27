USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

CREATE TABLE IF NOT EXISTS vendor_business_unit_assignment (
  assignment_id STRING,
  vendor_id STRING,
  business_unit_id STRING,
  source_system STRING,
  source_key STRING,
  effective_start_at TIMESTAMP,
  effective_end_at TIMESTAMP,
  is_primary BOOLEAN,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  created_by STRING,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS offering_business_unit_assignment (
  assignment_id STRING,
  offering_id STRING,
  business_unit_id STRING,
  source_system STRING,
  source_key STRING,
  effective_start_at TIMESTAMP,
  effective_end_at TIMESTAMP,
  is_primary BOOLEAN,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  created_by STRING,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_owner_assignment (
  assignment_id STRING,
  vendor_id STRING,
  owner_role_id STRING,
  user_principal STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  ended_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS offering_owner_assignment (
  assignment_id STRING,
  offering_id STRING,
  owner_role_id STRING,
  user_principal STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  ended_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS project_owner_assignment (
  assignment_id STRING,
  project_id STRING,
  owner_role_id STRING,
  user_principal STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  ended_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_contact (
  vendor_contact_id STRING,
  vendor_id STRING,
  contact_type_id STRING,
  full_name STRING,
  email STRING,
  phone STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  ended_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS offering_contact (
  offering_contact_id STRING,
  offering_id STRING,
  contact_type_id STRING,
  full_name STRING,
  email STRING,
  phone STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  ended_at TIMESTAMP
) USING DELTA;
