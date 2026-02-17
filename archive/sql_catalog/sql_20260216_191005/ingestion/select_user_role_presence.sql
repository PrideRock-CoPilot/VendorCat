SELECT 1 AS has_role
FROM {sec_user_role_map}
WHERE user_principal = %s
  AND active_flag = true
  AND revoked_at IS NULL
LIMIT 1
