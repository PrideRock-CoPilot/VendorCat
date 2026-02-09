(
p.project_id IN (
SELECT project_id FROM {app_project_vendor_map}
WHERE vendor_id = %s AND coalesce(active_flag, true) = true)
 OR p.vendor_id = %s
)
