UPDATE {app_offering_invoice}
SET
  active_flag = false,
  updated_at = %s,
  updated_by = %s
WHERE invoice_id = %s
  AND offering_id = %s
  AND vendor_id = %s
  AND coalesce(active_flag, true) = true
