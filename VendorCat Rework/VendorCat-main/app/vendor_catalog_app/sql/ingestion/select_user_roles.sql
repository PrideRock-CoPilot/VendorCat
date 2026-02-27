SELECT DISTINCT role_code
FROM {sec_user_role_map}
WHERE user_principal = %s
  AND active_flag = true
  AND revoked_at IS NULL
