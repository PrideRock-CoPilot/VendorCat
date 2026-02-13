SELECT
  c.vendor_id,
  c.contact_type,
  c.full_name,
  c.email,
  c.phone,
  c.active_flag,
  coalesce(v.display_name, v.legal_name, c.vendor_id) AS vendor_display_name,
  v.legal_name
FROM {core_vendor_contact} c
LEFT JOIN {core_vendor} v
  ON c.vendor_id = v.vendor_id
WHERE coalesce(c.active_flag, true) = true
ORDER BY lower(coalesce(v.display_name, v.legal_name, c.vendor_id)), lower(coalesce(c.full_name, ''))
LIMIT {limit}
