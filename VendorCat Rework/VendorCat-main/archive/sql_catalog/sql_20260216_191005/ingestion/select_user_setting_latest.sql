SELECT setting_value_json
FROM {app_user_settings}
WHERE user_principal = %s
  AND setting_key = %s
ORDER BY updated_at DESC
LIMIT 1
