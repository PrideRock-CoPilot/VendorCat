SELECT
  o.offering_id,
  o.vendor_id,
  o.offering_name,
  o.offering_type,
  o.business_unit,
  o.service_type,
  o.lifecycle_state,
  o.criticality_tier,
  coalesce(v.display_name, v.legal_name, o.vendor_id) AS vendor_display_name
FROM {core_vendor_offering} o
LEFT JOIN {core_vendor} v
  ON o.vendor_id = v.vendor_id
WHERE o.offering_id IN ({offering_ids_placeholders})

