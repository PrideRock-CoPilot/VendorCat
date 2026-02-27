INSERT INTO {sec_group_role_map}
  (group_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
VALUES
  (%s, %s, %s, %s, %s, %s)
