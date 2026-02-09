SELECT 1 AS present
FROM {core_vendor_offering}
WHERE vendor_id = %s
  AND offering_id = %s
LIMIT 1
