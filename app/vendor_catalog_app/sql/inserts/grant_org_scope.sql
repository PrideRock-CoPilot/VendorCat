INSERT INTO {sec_user_org_scope}
  (user_principal, org_id, scope_level, active_flag, granted_at)
VALUES
  (%s, %s, %s, %s, %s)
