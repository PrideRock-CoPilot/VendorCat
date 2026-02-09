SELECT
  o.offering_id,
  o.offering_name,
  obo.offering_owner_id,
  obo.owner_user_principal,
  obo.owner_role,
  obo.active_flag
FROM {core_offering_business_owner} obo
INNER JOIN {core_vendor_offering} o
  ON obo.offering_id = o.offering_id
WHERE o.vendor_id = %s
ORDER BY o.offering_name, obo.active_flag DESC
