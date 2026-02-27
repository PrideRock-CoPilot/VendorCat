SELECT n.demo_note_id, n.demo_id, n.note_type, n.note_text, n.created_at, n.created_by
FROM {core_vendor_demo_note} n
INNER JOIN {core_vendor_demo} d
  ON n.demo_id = d.demo_id
WHERE d.vendor_id = %s
ORDER BY n.created_at DESC
