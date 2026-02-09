SELECT
  o.offering_id,
  o.vendor_id,
  o.offering_name,
  o.offering_type,
  o.lifecycle_state,
  o.criticality_tier
FROM {app_project_offering_map} m
INNER JOIN {core_vendor_offering} o
  ON m.offering_id = o.offering_id
WHERE m.project_id = %s
  {vendor_clause}
  AND coalesce(m.active_flag, true) = true
ORDER BY o.offering_name
