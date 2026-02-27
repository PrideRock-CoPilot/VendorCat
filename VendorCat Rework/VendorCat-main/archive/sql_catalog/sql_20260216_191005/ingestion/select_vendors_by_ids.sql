SELECT vendor_id, display_name, legal_name, lifecycle_state, owner_org_id, risk_tier
FROM {core_vendor}
WHERE vendor_id IN ({vendor_ids_placeholders})
