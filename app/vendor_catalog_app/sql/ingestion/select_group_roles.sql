SELECT DISTINCT role_code
FROM {sec_group_role_map}
WHERE lower(group_principal) IN ({group_placeholders})
  AND active_flag = true
  AND revoked_at IS NULL
