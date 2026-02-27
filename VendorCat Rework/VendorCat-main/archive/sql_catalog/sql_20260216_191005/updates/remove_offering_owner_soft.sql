UPDATE {core_offering_business_owner}
SET active_flag = false
WHERE offering_owner_id = %s
  AND offering_id = %s
