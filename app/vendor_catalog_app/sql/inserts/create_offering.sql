INSERT INTO {core_vendor_offering}
  (offering_id, vendor_id, offering_name, offering_type, lifecycle_state, criticality_tier)
VALUES
  (%s, %s, %s, %s, %s, %s)
