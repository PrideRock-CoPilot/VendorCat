UPDATE {core_contract}
SET {set_clause},
    updated_at = %s,
    updated_by = %s
WHERE contract_id = %s
  AND vendor_id = %s
