SELECT
  o.vendor_owner_id,
  o.vendor_id,
  coalesce(u.login_identifier, o.owner_user_principal) AS owner_user_principal,
  o.owner_role,
  o.active_flag
FROM {core_vendor_business_owner} o
LEFT JOIN {app_user_directory} u
  ON lower(o.owner_user_principal) = lower(u.user_id)
WHERE o.vendor_id = %s
ORDER BY o.active_flag DESC, o.owner_role
