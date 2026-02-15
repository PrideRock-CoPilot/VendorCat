UPDATE {sec_user_role_map}
SET active_flag = ?,
    revoked_at = ?
WHERE user_principal = ?
  AND active_flag = true
  AND revoked_at IS NULL
