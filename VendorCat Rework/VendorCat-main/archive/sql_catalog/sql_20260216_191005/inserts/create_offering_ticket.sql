INSERT INTO {app_offering_ticket}
  (
    ticket_id,
    offering_id,
    vendor_id,
    ticket_system,
    external_ticket_id,
    title,
    status,
    priority,
    opened_date,
    closed_date,
    notes,
    active_flag,
    created_at,
    created_by,
    updated_at,
    updated_by
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
