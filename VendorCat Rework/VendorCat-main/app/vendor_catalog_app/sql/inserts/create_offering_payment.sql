INSERT INTO {app_offering_payment}
  (
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
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
