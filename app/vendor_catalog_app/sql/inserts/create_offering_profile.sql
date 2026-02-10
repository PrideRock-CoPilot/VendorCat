INSERT INTO {app_offering_profile}
  (
    offering_id,
    vendor_id,
    estimated_monthly_cost,
    implementation_notes,
    data_sent,
    data_received,
    integration_method,
    inbound_method,
    inbound_landing_zone,
    inbound_identifiers,
    inbound_reporting_layer,
    inbound_ingestion_notes,
    outbound_method,
    outbound_creation_process,
    outbound_delivery_process,
    outbound_responsible_owner,
    outbound_notes,
    updated_at,
    updated_by
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
