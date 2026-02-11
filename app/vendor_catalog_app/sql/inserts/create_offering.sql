INSERT INTO {core_vendor_offering}
  (
    offering_id,
    vendor_id,
    offering_name,
    offering_type,
    lob,
    service_type,
    lifecycle_state,
    criticality_tier,
    updated_at,
    updated_by
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
