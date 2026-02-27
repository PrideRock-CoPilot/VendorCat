SELECT
  o.offering_id,
  o.vendor_id,
  coalesce(v.display_name, v.legal_name, o.vendor_id) AS vendor_display_name,
  o.offering_name,
  o.lifecycle_state,
  p.estimated_monthly_cost
FROM {core_vendor_offering} o
LEFT JOIN {core_vendor} v
  ON o.vendor_id = v.vendor_id
LEFT JOIN {app_offering_profile} p
  ON p.offering_id = o.offering_id
 AND p.vendor_id = o.vendor_id
WHERE {where_clause}
ORDER BY lower(coalesce(v.display_name, v.legal_name, o.vendor_id)), lower(coalesce(o.offering_name, o.offering_id))
LIMIT {limit}
