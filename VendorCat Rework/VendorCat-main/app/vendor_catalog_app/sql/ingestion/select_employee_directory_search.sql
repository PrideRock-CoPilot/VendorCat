SELECT
  login_identifier,
  email,
  network_id,
  employee_id,
  manager_id,
  first_name,
  last_name,
  display_name
FROM {employee_directory_view}
WHERE coalesce(active_flag, true) = true
  AND (
    %s = ''
    OR lower(coalesce(login_identifier, '')) LIKE %s
    OR lower(coalesce(display_name, '')) LIKE %s
    OR lower(coalesce(email, '')) LIKE %s
    OR lower(coalesce(network_id, '')) LIKE %s
    OR lower(coalesce(employee_id, '')) LIKE %s
    OR lower(coalesce(manager_id, '')) LIKE %s
    OR lower(coalesce(first_name, '')) LIKE %s
    OR lower(coalesce(last_name, '')) LIKE %s
  )
ORDER BY display_name, login_identifier
LIMIT {limit}
