SELECT
  user_id,
  login_identifier,
  display_name
FROM {app_user_directory}
ORDER BY display_name, login_identifier
