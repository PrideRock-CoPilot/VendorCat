SELECT DISTINCT owner_org_id AS org_id
FROM {core_vendor}
WHERE owner_org_id IS NOT NULL
ORDER BY owner_org_id
