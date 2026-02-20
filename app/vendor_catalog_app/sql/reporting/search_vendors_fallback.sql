SELECT vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, updated_at
FROM {core_vendor} v
WHERE (
  lower(v.legal_name) LIKE lower(%s)
  OR lower(coalesce(v.display_name, '')) LIKE lower(%s)
  OR lower(v.vendor_id) LIKE lower(%s)
)
{state_clause}
{merged_clause}
ORDER BY v.display_name
LIMIT 250
