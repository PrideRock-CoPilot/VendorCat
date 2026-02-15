SELECT note_id, entity_name, entity_id, note_type, note_text, created_at, created_by
FROM {app_note}
WHERE note_id = %s
LIMIT 1
