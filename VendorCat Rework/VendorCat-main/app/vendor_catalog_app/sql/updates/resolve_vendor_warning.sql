UPDATE {app_vendor_warning}
SET warning_status = %s,
    resolved_at = %s,
    updated_at = %s,
    updated_by = %s
WHERE warning_id = %s
  AND vendor_id = %s
