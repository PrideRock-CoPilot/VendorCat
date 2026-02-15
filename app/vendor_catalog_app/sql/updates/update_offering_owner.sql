UPDATE {core_offering_business_owner}
SET
  owner_user_principal = %s,
  owner_role = %s,
  updated_at = %s,
  updated_by = %s
WHERE offering_owner_id = %s
  AND offering_id = %s
