INSERT INTO {sec_role_permission}
  (role_code, object_name, action_code, active_flag, updated_at)
VALUES
  (%s, %s, %s, %s, %s)
