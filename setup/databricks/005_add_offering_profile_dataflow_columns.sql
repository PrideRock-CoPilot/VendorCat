-- Migration for deployments where app_offering_profile exists without data flow columns

ALTER TABLE {fq_schema}.app_offering_profile
ADD COLUMNS (
  inbound_method STRING,
  inbound_landing_zone STRING,
  inbound_identifiers STRING,
  inbound_reporting_layer STRING,
  inbound_ingestion_notes STRING,
  outbound_method STRING,
  outbound_creation_process STRING,
  outbound_delivery_process STRING,
  outbound_responsible_owner STRING,
  outbound_notes STRING
);
