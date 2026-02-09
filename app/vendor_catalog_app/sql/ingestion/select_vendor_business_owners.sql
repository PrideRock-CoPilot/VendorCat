SELECT vendor_owner_id, vendor_id, owner_user_principal, owner_role, active_flag
FROM {core_vendor_business_owner}
WHERE vendor_id = %s
ORDER BY active_flag DESC, owner_role
