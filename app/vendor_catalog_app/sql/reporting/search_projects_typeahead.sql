SELECT
  p.project_id,
  p.project_name,
  p.status,
  p.vendor_id,
  coalesce(v.display_name, v.legal_name, p.vendor_id, 'Unassigned') AS vendor_display_name,
  coalesce(p.project_name, p.project_id)
    || ' (' || p.project_id || ') - '
    || coalesce(v.display_name, v.legal_name, p.vendor_id, 'Unassigned') AS label
FROM {app_project} p
LEFT JOIN {core_vendor} v
  ON p.vendor_id = v.vendor_id
WHERE {where_clause}
ORDER BY p.updated_at DESC, p.project_name
LIMIT {limit}
