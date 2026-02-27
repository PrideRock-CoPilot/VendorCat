SELECT
  coalesce(u.login_identifier, s.user_principal) AS user_principal,
  coalesce(u.display_name, u.login_identifier, s.user_principal) AS user_display_name,
  s.org_id,
  s.scope_level,
  s.active_flag,
  s.granted_at
FROM {sec_user_org_scope} s
LEFT JOIN {app_user_directory} u
  ON lower(s.user_principal) = lower(u.user_id)
WHERE
  (%s = '' OR lower(coalesce(u.login_identifier, s.user_principal)) = %s)
  AND (%s = '' OR lower(s.org_id) = %s)
  AND (
    %s = ''
    OR lower(coalesce(u.login_identifier, s.user_principal)) LIKE %s
    OR lower(s.org_id) LIKE %s
    OR lower(s.scope_level) LIKE %s
  )
ORDER BY s.granted_at DESC
LIMIT {limit}
OFFSET {offset}
