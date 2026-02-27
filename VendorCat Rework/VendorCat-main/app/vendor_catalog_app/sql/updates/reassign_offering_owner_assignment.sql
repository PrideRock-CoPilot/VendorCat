UPDATE {core_offering_business_owner}
SET owner_user_principal = %s,
    updated_at = %s,
    updated_by = %s
WHERE offering_owner_id = %s
  AND coalesce(active_flag, true) = true
