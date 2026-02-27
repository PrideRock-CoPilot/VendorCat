SELECT DISTINCT
  v.vendor_id,
  v.legal_name,
  v.display_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  v.source_system,
  v.updated_at
FROM {core_vendor} v
WHERE {where_clause}
ORDER BY {sort_expr} {sort_dir}, lower(v.vendor_id) ASC
LIMIT %s OFFSET %s
