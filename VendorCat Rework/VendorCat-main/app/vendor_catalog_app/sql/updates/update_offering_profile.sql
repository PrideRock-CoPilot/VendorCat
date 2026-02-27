UPDATE {app_offering_profile}
SET
  estimated_monthly_cost = %s,
  implementation_notes = %s,
  data_sent = %s,
  data_received = %s,
  integration_method = %s,
  inbound_method = %s,
  inbound_landing_zone = %s,
  inbound_identifiers = %s,
  inbound_reporting_layer = %s,
  inbound_ingestion_notes = %s,
  outbound_method = %s,
  outbound_creation_process = %s,
  outbound_delivery_process = %s,
  outbound_responsible_owner = %s,
  outbound_notes = %s,
  updated_at = %s,
  updated_by = %s
WHERE offering_id = %s
  AND vendor_id = %s
