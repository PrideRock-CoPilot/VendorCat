SELECT
  offering_id,
  vendor_id,
  offering_name,
  offering_type,
  business_unit,
  service_type,
  lifecycle_state,
  criticality_tier
FROM {core_vendor_offering}
WHERE vendor_id = %s
ORDER BY offering_name

