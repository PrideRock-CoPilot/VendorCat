INSERT INTO {audit_workflow_event}
  (workflow_event_id, workflow_type, workflow_id, old_status, new_status, actor_user_principal, event_ts, notes)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s)
