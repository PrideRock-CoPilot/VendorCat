SELECT
  invoice_id,
  offering_id,
  vendor_id,
  invoice_number,
  invoice_date,
  amount,
  currency_code,
  invoice_status,
  notes,
  active_flag,
  created_at,
  created_by,
  updated_at,
  updated_by
FROM {app_offering_invoice}
WHERE {where_clause}
ORDER BY updated_at DESC, created_at DESC
LIMIT %s
