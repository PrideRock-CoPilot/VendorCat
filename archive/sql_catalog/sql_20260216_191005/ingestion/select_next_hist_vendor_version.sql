SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version
FROM {hist_vendor}
WHERE vendor_id = %s
