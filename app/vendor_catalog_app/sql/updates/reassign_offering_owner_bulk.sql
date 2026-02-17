UPDATE {core_offering_business_owner} AS obo
SET
  owner_user_principal = %s,
  updated_at = %s,
  updated_by = %s
WHERE
  lower(obo.owner_user_principal) = lower(%s)
  AND (
    obo.active_flag = true
    OR obo.active_flag = 1
  )
  AND EXISTS (
    SELECT 1
    FROM {core_vendor_offering} AS o
    WHERE o.offering_id = obo.offering_id
      AND o.vendor_id = %s
  );
