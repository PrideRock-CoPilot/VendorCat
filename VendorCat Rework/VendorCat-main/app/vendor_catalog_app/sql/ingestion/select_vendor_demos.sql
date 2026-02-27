SELECT demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes
FROM {core_vendor_demo}
WHERE vendor_id = %s
ORDER BY demo_date DESC
