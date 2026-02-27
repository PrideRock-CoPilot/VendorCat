INSERT INTO {app_offering_invoice}
  (
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
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
