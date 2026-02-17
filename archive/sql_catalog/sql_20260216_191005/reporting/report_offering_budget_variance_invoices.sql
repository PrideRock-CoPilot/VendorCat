SELECT
  invoice_id,
  offering_id,
  vendor_id,
  invoice_date,
  amount,
  invoice_status
FROM {app_offering_invoice}
WHERE coalesce(active_flag, true) = true
  AND offering_id IN ({offering_ids_placeholders})
