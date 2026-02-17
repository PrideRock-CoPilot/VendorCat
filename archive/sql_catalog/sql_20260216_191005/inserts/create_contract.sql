INSERT INTO {core_contract}
  (
    contract_id,
    vendor_id,
    offering_id,
    contract_number,
    contract_status,
    start_date,
    end_date,
    cancelled_flag,
    annual_value,
    updated_at,
    updated_by
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
