SELECT demo_note_id, demo_id, note_type, note_text, created_at, created_by
FROM {core_vendor_demo_note}
WHERE demo_id = %s
  AND lower(note_type) = lower(%s)
  AND lower(created_by) = lower(%s)
ORDER BY created_at DESC
LIMIT {limit}
