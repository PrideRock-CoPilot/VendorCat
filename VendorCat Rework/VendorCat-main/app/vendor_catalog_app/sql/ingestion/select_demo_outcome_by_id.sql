SELECT demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes, updated_at, updated_by
FROM {core_vendor_demo}
WHERE demo_id = %s
LIMIT 1
