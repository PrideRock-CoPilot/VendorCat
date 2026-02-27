INSERT INTO {app_user_settings}
  (setting_id, user_principal, setting_key, setting_value_json, updated_at, updated_by)
VALUES
  (%s, %s, %s, %s, %s, %s)
