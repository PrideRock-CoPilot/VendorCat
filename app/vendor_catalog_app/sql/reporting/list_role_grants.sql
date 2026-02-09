SELECT user_principal, role_code, active_flag, granted_by, granted_at, revoked_at
FROM {sec_user_role_map}
ORDER BY granted_at DESC
LIMIT 1000
