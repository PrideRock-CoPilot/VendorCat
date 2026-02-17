SELECT
  role_code,
  role_name,
  description,
  approval_level,
  can_edit,
  can_report,
  can_direct_apply,
  active_flag,
  updated_at,
  updated_by
FROM {sec_role_definition}
ORDER BY role_code
