SELECT e.contract_event_id, e.contract_id, e.event_type, e.event_ts, e.reason_code, e.notes, e.actor_user_principal
FROM {core_contract_event} e
INNER JOIN {core_contract} c
  ON e.contract_id = c.contract_id
WHERE c.vendor_id = %s
ORDER BY e.event_ts DESC
