SELECT contract_id, vendor_id, offering_id, contract_number, contract_status, start_date, end_date, cancelled_flag
FROM {core_contract}
WHERE vendor_id = %s
ORDER BY end_date DESC
