SELECT user_principal, org_id, scope_level, active_flag, granted_at
FROM {sec_user_org_scope}
ORDER BY granted_at DESC
LIMIT 1000
