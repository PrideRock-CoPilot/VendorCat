SELECT
  count(*) AS total_count
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
