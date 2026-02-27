INSERT INTO {audit_entity_change}
  (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
