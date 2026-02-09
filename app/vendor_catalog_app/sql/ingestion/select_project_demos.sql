SELECT
  project_demo_id,
  project_id,
  vendor_id,
  demo_name,
  demo_datetime_start,
  demo_datetime_end,
  demo_type,
  outcome,
  score,
  attendees_internal,
  attendees_vendor,
  notes,
  followups,
  linked_offering_id,
  linked_vendor_demo_id,
  created_at,
  created_by,
  updated_at,
  updated_by
FROM {app_project_demo}
WHERE project_id = %s
  {vendor_clause}
  AND coalesce(active_flag, true) = true
ORDER BY updated_at DESC
