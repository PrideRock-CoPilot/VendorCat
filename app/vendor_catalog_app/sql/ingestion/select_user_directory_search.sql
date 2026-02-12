SELECT
  user_id,
  login_identifier,
  display_name
FROM {app_user_directory}
WHERE (
  %s = ''
  OR lower(coalesce(login_identifier, '')) LIKE %s
  OR lower(coalesce(display_name, '')) LIKE %s
)
ORDER BY display_name, login_identifier
LIMIT {limit}
