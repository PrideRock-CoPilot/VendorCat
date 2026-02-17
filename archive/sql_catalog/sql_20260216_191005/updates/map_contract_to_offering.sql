UPDATE {core_contract}
SET offering_id = %s,
    updated_at = %s,
    updated_by = %s
WHERE contract_id = %s
  AND vendor_id = %s
