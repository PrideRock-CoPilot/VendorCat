SELECT role_code
FROM {sec_role_definition}
WHERE role_code = %s
LIMIT 1
