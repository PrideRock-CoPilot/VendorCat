INSERT INTO {audit_access_event}
  (access_event_id, actor_user_principal, action_type, target_user_principal, target_role, event_ts, notes)
VALUES
  (%s, %s, %s, %s, %s, %s, %s)
