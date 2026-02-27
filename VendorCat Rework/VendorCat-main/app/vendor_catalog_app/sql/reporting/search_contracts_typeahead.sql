SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  c.contract_number,
  c.contract_status,
  coalesce(v.display_name, v.legal_name, c.vendor_id) AS vendor_display_name,
  coalesce(o.offering_name, c.offering_id, 'Unassigned') AS offering_name,
  coalesce(c.contract_number, c.contract_id)
    || ' (' || c.contract_id || ') - '
    || coalesce(v.display_name, v.legal_name, c.vendor_id)
    || CASE
         WHEN coalesce(o.offering_name, c.offering_id, '') <> '' THEN ' / ' || coalesce(o.offering_name, c.offering_id)
         ELSE ''
       END AS label
FROM {core_contract} c
LEFT JOIN {core_vendor} v
  ON c.vendor_id = v.vendor_id
LEFT JOIN {core_vendor_offering} o
  ON c.offering_id = o.offering_id
WHERE {where_clause}
ORDER BY c.updated_at DESC, lower(coalesce(c.contract_number, c.contract_id))
LIMIT {limit}
