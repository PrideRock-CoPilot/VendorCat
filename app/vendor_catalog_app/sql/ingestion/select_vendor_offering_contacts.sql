SELECT
  o.offering_id,
  o.offering_name,
  c.offering_contact_id,
  c.contact_type,
  c.full_name,
  c.email,
  c.phone,
  c.active_flag
FROM {core_offering_contact} c
INNER JOIN {core_vendor_offering} o
  ON c.offering_id = o.offering_id
WHERE o.vendor_id = %s
ORDER BY o.offering_name, c.full_name
