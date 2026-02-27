SELECT
  c.contract_id,
  c.vendor_id,
  coalesce(v.display_name, v.legal_name, c.vendor_id) AS vendor_display_name,
  c.offering_id,
  coalesce(o.offering_name, c.offering_id, 'Unassigned') AS offering_name,
  c.contract_number,
  c.contract_status,
  c.start_date,
  c.end_date,
  c.cancelled_flag,
  c.annual_value,
  c.updated_at
FROM {core_contract} c
LEFT JOIN {core_vendor} v
  ON c.vendor_id = v.vendor_id
LEFT JOIN {core_vendor_offering} o
  ON c.offering_id = o.offering_id
WHERE {where_clause}
ORDER BY
  CASE
    WHEN c.end_date IS NULL THEN 1
    ELSE 0
  END,
  c.end_date ASC,
  lower(coalesce(v.display_name, v.legal_name, c.vendor_id)),
  lower(coalesce(c.contract_number, c.contract_id))
LIMIT {limit}
