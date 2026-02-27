UPDATE {sec_user_org_scope}
SET active_flag = ?
WHERE user_principal = ?
  AND org_id = ?
  AND scope_level = ?
  AND active_flag = true
