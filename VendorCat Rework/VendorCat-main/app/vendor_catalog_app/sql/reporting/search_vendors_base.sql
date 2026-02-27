SELECT vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, updated_at
FROM {core_vendor} v
WHERE 1 = 1
{state_clause}
ORDER BY display_name
LIMIT 250
