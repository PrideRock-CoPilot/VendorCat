SELECT
  login_identifier,
  email,
  network_id,
  employee_id,
  manager_id,
  first_name,
  last_name,
  display_name,
  active_flag
FROM {employee_directory_view}
WHERE
  lower(coalesce(login_identifier, '')) = lower(%s)
  OR lower(coalesce(email, '')) = lower(%s)
  OR lower(coalesce(network_id, '')) = lower(%s)
  OR lower(coalesce(employee_id, '')) = lower(%s)
ORDER BY
  CASE
    WHEN lower(coalesce(active_flag || '', '1')) IN ('1', 'a', 'active', 'true') THEN 0
    ELSE 1
  END,
  login_identifier
LIMIT 1
