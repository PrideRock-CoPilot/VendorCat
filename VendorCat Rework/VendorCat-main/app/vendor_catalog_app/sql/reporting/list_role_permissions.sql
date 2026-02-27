SELECT
  role_code,
  object_name,
  action_code,
  active_flag,
  updated_at
FROM {sec_role_permission}
ORDER BY role_code, object_name, action_code
