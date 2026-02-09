INSERT INTO {app_usage_log}
  (usage_event_id, user_principal, page_name, event_type, event_ts, payload_json)
VALUES
  (%s, %s, %s, %s, %s, %s)
