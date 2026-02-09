UPDATE {core_vendor_demo}
SET offering_id = %s,
    updated_at = %s,
    updated_by = %s
WHERE demo_id = %s
  AND vendor_id = %s
