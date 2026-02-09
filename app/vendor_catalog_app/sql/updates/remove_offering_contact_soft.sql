UPDATE {core_offering_contact}
SET active_flag = false
WHERE offering_contact_id = %s
  AND offering_id = %s
