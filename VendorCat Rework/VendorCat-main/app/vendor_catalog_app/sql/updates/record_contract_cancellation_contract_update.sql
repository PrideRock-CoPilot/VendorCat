UPDATE {core_contract}
SET contract_status = %s,
    cancelled_flag = %s,
    updated_at = %s,
    updated_by = %s
WHERE contract_id = %s
