SELECT
  count(*) AS total_count
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
