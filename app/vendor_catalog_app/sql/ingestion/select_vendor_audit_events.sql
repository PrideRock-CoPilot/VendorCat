SELECT change_event_id, entity_name, entity_id, action_type, event_ts, actor_user_principal, request_id
FROM {audit_entity_change}
WHERE entity_id = %s
   OR request_id IN (
        SELECT change_request_id
        FROM {app_vendor_change_request}
        WHERE vendor_id = %s
   )
ORDER BY event_ts DESC
LIMIT 500
