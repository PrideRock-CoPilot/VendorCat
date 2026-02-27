UPDATE {sec_group_role_map}
SET active_flag = ?,
    revoked_at = ?
WHERE lower(group_principal) = lower(?)
  AND role_code = ?
  AND active_flag = true
  AND revoked_at IS NULL
