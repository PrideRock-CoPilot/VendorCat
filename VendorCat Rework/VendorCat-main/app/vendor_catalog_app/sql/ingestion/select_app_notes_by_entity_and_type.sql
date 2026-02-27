SELECT note_id, entity_name, entity_id, note_type, note_text, created_at, created_by
FROM {app_note}
WHERE lower(entity_name) = lower(%s)
  AND lower(note_type) = lower(%s)
ORDER BY created_at DESC
LIMIT {limit}
