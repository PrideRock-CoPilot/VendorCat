UPDATE {sec_role_definition}
SET role_name = %s,
    description = %s,
    approval_level = %s,
    can_edit = %s,
    can_report = %s,
    can_direct_apply = %s,
    active_flag = %s,
    updated_at = %s,
    updated_by = %s
WHERE role_code = %s
