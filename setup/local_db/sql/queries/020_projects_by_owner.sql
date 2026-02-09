-- Replace ? with owner principal, for example: bob.smith@example.com
SELECT
  p.project_id,
  p.project_name,
  p.status,
  p.start_date,
  p.target_date,
  p.owner_principal,
  v.vendor_id,
  COALESCE(v.display_name, v.legal_name) AS vendor_name,
  COUNT(DISTINCT pd.project_demo_id) AS demo_count
FROM app_project p
INNER JOIN core_vendor v ON v.vendor_id = p.vendor_id
LEFT JOIN app_project_demo pd
  ON pd.project_id = p.project_id
 AND COALESCE(pd.active_flag, 1) = 1
WHERE COALESCE(p.active_flag, 1) = 1
  AND LOWER(COALESCE(p.owner_principal, '')) = LOWER(?)
GROUP BY p.project_id, p.project_name, p.status, p.start_date, p.target_date, p.owner_principal, v.vendor_id, COALESCE(v.display_name, v.legal_name)
ORDER BY p.target_date IS NULL, p.target_date, p.project_name;
