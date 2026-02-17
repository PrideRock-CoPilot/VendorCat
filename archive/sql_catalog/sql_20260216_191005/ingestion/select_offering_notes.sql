SELECT
  note_id,
  entity_name,
  entity_id,
  note_type,
  note_text,
  created_at,
  created_by
FROM {app_note}
WHERE entity_name = 'offering'
  AND entity_id = %s
  {note_type_clause}
ORDER BY created_at DESC
