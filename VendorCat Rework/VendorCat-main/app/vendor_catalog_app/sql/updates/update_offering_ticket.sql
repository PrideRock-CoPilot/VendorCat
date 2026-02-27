UPDATE {app_offering_ticket}
SET
  {set_clause},
  updated_at = %s,
  updated_by = %s
WHERE ticket_id = %s
  AND offering_id = %s
  AND vendor_id = %s
  AND coalesce(active_flag, true) = true
