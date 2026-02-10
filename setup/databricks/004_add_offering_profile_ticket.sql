-- Migration for existing deployments to support offering operations profile and ticket tracking

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_profile (
  offering_id STRING NOT NULL,
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
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_ticket (
  ticket_id STRING NOT NULL,
  offering_id STRING NOT NULL,
  vendor_id STRING NOT NULL,
  ticket_system STRING,
  external_ticket_id STRING,
  title STRING NOT NULL,
  status STRING NOT NULL,
  priority STRING,
  opened_date DATE,
  closed_date DATE,
  notes STRING,
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;
