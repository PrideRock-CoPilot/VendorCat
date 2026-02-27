UPDATE {hist_vendor}
SET is_current = false,
    valid_to_ts = %s
WHERE vendor_id = %s
  AND is_current = true
