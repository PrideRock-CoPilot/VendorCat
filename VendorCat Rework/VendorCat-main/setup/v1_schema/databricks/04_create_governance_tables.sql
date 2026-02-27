USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

CREATE TABLE IF NOT EXISTS change_request (
  request_id STRING,
  entity_type STRING,
  entity_id STRING,
  change_type STRING,
  payload_json STRING,
  request_status STRING,
  created_at TIMESTAMP,
  created_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_merge_event (
  merge_id STRING,
  survivor_vendor_id STRING,
  merge_status STRING,
  merge_reason STRING,
  merge_method STRING,
  confidence_score DOUBLE,
  request_id STRING,
  merged_at TIMESTAMP,
  merged_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_merge_member (
  merge_member_id STRING,
  merge_id STRING,
  vendor_id STRING,
  member_role STRING,
  source_system_code STRING,
  source_vendor_key STRING,
  pre_merge_display_name STRING,
  active_flag BOOLEAN,
  created_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_merge_snapshot (
  snapshot_id STRING,
  merge_id STRING,
  vendor_id STRING,
  snapshot_json STRING,
  captured_at TIMESTAMP,
  captured_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS vendor_survivorship_decision (
  decision_id STRING,
  merge_id STRING,
  field_name STRING,
  chosen_vendor_id STRING,
  chosen_value_text STRING,
  decision_method STRING,
  decision_note STRING,
  decided_at TIMESTAMP,
  decided_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS change_event (
  event_id STRING,
  request_id STRING,
  entity_type STRING,
  entity_id STRING,
  action STRING,
  payload_json STRING,
  created_at TIMESTAMP,
  created_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS schema_version (
  version_num INT,
  description STRING,
  applied_at TIMESTAMP,
  applied_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS custom_attribute_definition (
  definition_id STRING,
  scope STRING,
  attribute_key STRING,
  attribute_label STRING,
  data_type STRING,
  validation_rule STRING,
  lookup_type STRING,
  is_required BOOLEAN,
  is_active BOOLEAN,
  created_at TIMESTAMP,
  created_by STRING,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS custom_attribute_value (
  attribute_value_id STRING,
  scope STRING,
  entity_id STRING,
  definition_id STRING,
  value_text STRING,
  value_number DOUBLE,
  value_date DATE,
  value_bool BOOLEAN,
  updated_at TIMESTAMP,
  updated_by STRING
) USING DELTA;
