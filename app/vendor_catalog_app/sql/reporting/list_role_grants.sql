SELECT
  coalesce(u.login_identifier, g.user_principal) AS user_principal,
  g.role_code,
  g.active_flag,
  coalesce(gr.login_identifier, g.granted_by) AS granted_by,
  g.granted_at,
  g.revoked_at
FROM {sec_user_role_map} g
LEFT JOIN {app_user_directory} u
  ON lower(g.user_principal) = lower(u.user_id)
LEFT JOIN {app_user_directory} gr
  ON lower(g.granted_by) = lower(gr.user_id)
ORDER BY g.granted_at DESC
LIMIT 1000
