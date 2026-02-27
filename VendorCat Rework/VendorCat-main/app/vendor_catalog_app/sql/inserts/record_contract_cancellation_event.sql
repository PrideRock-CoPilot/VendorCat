INSERT INTO {core_contract_event}
  (contract_event_id, contract_id, event_type, event_ts, reason_code, notes, actor_user_principal)
VALUES
  (%s, %s, %s, %s, %s, %s, %s)
