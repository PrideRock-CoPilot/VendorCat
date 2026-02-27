DELETE FROM {app_user_settings}
WHERE user_principal = %s
  AND setting_key = %s
