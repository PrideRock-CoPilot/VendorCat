UPDATE {sec_role_permission}
SET active_flag = false,
    updated_at = %s
WHERE role_code = %s
