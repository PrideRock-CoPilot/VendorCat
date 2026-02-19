SELECT 1 AS has_approver
FROM (
  SELECT role_code
  FROM {sec_user_role_map}
  WHERE
    lower(coalesce(role_code, '')) IN ('vendor_admin', 'vendor_steward', 'vendor_approver')
    AND coalesce(active_flag, true) = true
    AND revoked_at IS NULL

  UNION ALL

  SELECT role_code
  FROM {sec_group_role_map}
  WHERE
    lower(coalesce(role_code, '')) IN ('vendor_admin', 'vendor_steward', 'vendor_approver')
    AND coalesce(active_flag, true) = true
    AND revoked_at IS NULL
) approvers
LIMIT 1
