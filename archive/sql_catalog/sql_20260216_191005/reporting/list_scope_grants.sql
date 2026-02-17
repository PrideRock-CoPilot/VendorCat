SELECT
  coalesce(u.login_identifier, s.user_principal) AS user_principal,
  s.org_id,
  s.scope_level,
  s.active_flag,
  s.granted_at
FROM {sec_user_org_scope} s
LEFT JOIN {app_user_directory} u
  ON lower(s.user_principal) = lower(u.user_id)
ORDER BY s.granted_at DESC
LIMIT 1000
