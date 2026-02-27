SELECT
  count(*) AS total_count
FROM {sec_group_role_map} g
LEFT JOIN {app_user_directory} gr
  ON lower(g.granted_by) = lower(gr.user_id)
WHERE
  (%s = '' OR lower(g.group_principal) = %s)
  AND (%s = '' OR lower(g.role_code) = %s)
  AND (
    %s = ''
    OR lower(g.group_principal) LIKE %s
    OR lower(g.role_code) LIKE %s
    OR lower(coalesce(gr.login_identifier, g.granted_by)) LIKE %s
  )
