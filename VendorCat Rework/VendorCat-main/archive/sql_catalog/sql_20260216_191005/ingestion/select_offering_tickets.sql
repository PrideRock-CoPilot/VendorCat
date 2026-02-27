SELECT
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
FROM {app_offering_ticket}
WHERE offering_id = %s
  AND vendor_id = %s
  AND coalesce(active_flag, true) = true
ORDER BY coalesce(opened_date, created_at) DESC, created_at DESC
