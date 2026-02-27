SELECT
  v.vendor_id,
  coalesce(v.display_name, v.legal_name, v.vendor_id) AS label,
  v.display_name,
  v.legal_name,
  v.lifecycle_state
FROM {core_vendor} v
WHERE {where_clause}
ORDER BY lower(coalesce(v.display_name, v.legal_name, v.vendor_id)), lower(v.vendor_id)
LIMIT {limit}
