SELECT
  coalesce(u.login_identifier, g.user_principal) AS user_principal,
  coalesce(u.display_name, u.login_identifier, g.user_principal) AS user_display_name,
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
WHERE
  (%s = '' OR lower(coalesce(u.login_identifier, g.user_principal)) = %s)
  AND (%s = '' OR lower(g.role_code) = %s)
  AND (
    %s = ''
    OR lower(coalesce(u.login_identifier, g.user_principal)) LIKE %s
    OR lower(g.role_code) LIKE %s
    OR lower(coalesce(gr.login_identifier, g.granted_by)) LIKE %s
  )
ORDER BY g.granted_at DESC
LIMIT {limit}
OFFSET {offset}
