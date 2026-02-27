SELECT
  o.offering_id,
  o.offering_name,
  obo.offering_owner_id,
  coalesce(u.login_identifier, obo.owner_user_principal) AS owner_user_principal,
  obo.owner_role,
  obo.active_flag
FROM {core_offering_business_owner} obo
INNER JOIN {core_vendor_offering} o
  ON obo.offering_id = o.offering_id
LEFT JOIN {app_user_directory} u
  ON lower(obo.owner_user_principal) = lower(u.user_id)
WHERE o.vendor_id = %s
ORDER BY o.offering_name, obo.active_flag DESC
