-- Migration for deployments where app_offering_data_flow does not yet exist

CREATE TABLE IF NOT EXISTS {fq_schema}.app_offering_data_flow (
  data_flow_id STRING NOT NULL,
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
  active_flag BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  created_by STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  updated_by STRING NOT NULL
) USING DELTA;

