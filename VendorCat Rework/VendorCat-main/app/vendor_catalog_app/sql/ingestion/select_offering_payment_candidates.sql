SELECT
  payment_id,
  invoice_id,
  offering_id,
  vendor_id,
  payment_reference,
  payment_date,
  amount,
  currency_code,
  payment_status,
  notes,
  active_flag,
  created_at,
  created_by,
  updated_at,
  updated_by
FROM {app_offering_payment}
WHERE {where_clause}
ORDER BY updated_at DESC, created_at DESC
LIMIT %s
