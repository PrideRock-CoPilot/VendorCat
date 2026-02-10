SELECT change_event_id, entity_name, entity_id, action_type, before_json, after_json, event_ts, actor_user_principal, request_id
FROM {audit_entity_change}
WHERE entity_id = %s
OR entity_id IN (
        SELECT project_demo_id
        FROM {app_project_demo}
        WHERE project_id = %s
          AND (%s IS NULL OR vendor_id = %s)
   )
   OR entity_id IN (
        SELECT doc_id
        FROM {app_document_link}
        WHERE entity_type = 'project'
          AND entity_id = %s
   )
OR entity_id IN (
        SELECT project_note_id
        FROM {app_project_note}
        WHERE project_id = %s
          AND (%s IS NULL OR vendor_id = %s)
   )
ORDER BY event_ts DESC
LIMIT 500
