SELECT
  change_event_id,
  entity_name,
  entity_id,
  action_type,
  before_json,
  after_json,
  event_ts,
  actor_user_principal,
  request_id
FROM {audit_entity_change}
WHERE entity_id = %s
   OR entity_id IN (
        SELECT data_flow_id
        FROM {app_offering_data_flow}
        WHERE offering_id = %s
          AND coalesce(active_flag, true) = true
   )
   OR entity_id IN (
        SELECT ticket_id
        FROM {app_offering_ticket}
        WHERE offering_id = %s
          AND coalesce(active_flag, true) = true
   )
   OR entity_id IN (
        SELECT note_id
        FROM {app_note}
        WHERE entity_name = 'offering'
          AND entity_id = %s
   )
   OR entity_id IN (
        SELECT doc_id
        FROM {app_document_link}
        WHERE entity_type = 'offering'
          AND entity_id = %s
          AND coalesce(active_flag, true) = true
   )
ORDER BY event_ts DESC
LIMIT 500
