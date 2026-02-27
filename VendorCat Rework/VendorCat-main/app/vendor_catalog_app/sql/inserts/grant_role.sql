INSERT INTO {sec_user_role_map}
  (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
VALUES
  (%s, %s, %s, %s, %s, %s)
