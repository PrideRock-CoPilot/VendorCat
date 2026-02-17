SELECT demo_note_id, demo_id, note_type, note_text, created_at, created_by
FROM {core_vendor_demo_note}
WHERE demo_note_id = %s
LIMIT 1
