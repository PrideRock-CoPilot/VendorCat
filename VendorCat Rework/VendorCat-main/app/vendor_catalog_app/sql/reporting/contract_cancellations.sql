SELECT contract_id, vendor_id, offering_id, cancelled_at, reason_code, notes
FROM {rpt_contract_cancellations}
ORDER BY cancelled_at DESC
LIMIT 500
