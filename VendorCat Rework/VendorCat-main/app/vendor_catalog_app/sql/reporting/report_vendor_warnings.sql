SELECT
  w.warning_id,
  w.vendor_id,
  coalesce(v.display_name, v.legal_name, v.vendor_id) AS vendor_display_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  w.warning_category,
  w.severity,
  w.warning_status,
  w.warning_title,
  w.warning_detail,
  w.source_table,
  w.source_version,
  w.file_name,
  w.detected_at,
  w.resolved_at,
  w.updated_at,
  w.updated_by
FROM {app_vendor_warning} w
INNER JOIN {core_vendor} v
  ON v.vendor_id = w.vendor_id
WHERE {where_clause}
ORDER BY coalesce(w.detected_at, w.created_at, w.updated_at) DESC, w.vendor_id
LIMIT {limit}
