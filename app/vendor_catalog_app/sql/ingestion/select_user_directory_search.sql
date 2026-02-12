SELECT
  user_id,
  login_identifier,
  display_name,
  email,
  first_name,
  last_name
FROM {app_user_directory}
WHERE coalesce(active_flag, true) = true
  AND (
  %s = ''
  OR lower(coalesce(login_identifier, '')) LIKE %s
  OR lower(coalesce(display_name, '')) LIKE %s
  OR lower(coalesce(email, '')) LIKE %s
  OR lower(coalesce(first_name, '')) LIKE %s
  OR lower(coalesce(last_name, '')) LIKE %s
)
ORDER BY display_name, login_identifier
LIMIT {limit}
