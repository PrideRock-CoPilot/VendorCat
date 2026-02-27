SELECT
  o.offering_id,
  o.vendor_id,
  o.offering_name,
  o.offering_type,
  o.lob,
  o.service_type,
  o.lifecycle_state,
  coalesce(v.display_name, v.legal_name, o.vendor_id) AS vendor_display_name,
  coalesce(o.offering_name, o.offering_id)
    || ' (' || o.offering_id || ') - '
    || coalesce(v.display_name, v.legal_name, o.vendor_id) AS label
FROM {core_vendor_offering} o
LEFT JOIN {core_vendor} v
  ON o.vendor_id = v.vendor_id
WHERE {where_clause}
ORDER BY lower(coalesce(v.display_name, v.legal_name, o.vendor_id)), lower(coalesce(o.offering_name, o.offering_id))
LIMIT {limit}
