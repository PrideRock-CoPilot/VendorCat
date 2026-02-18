USE CATALOG a1_dlk;
USE SCHEMA twvendor;

CREATE OR REPLACE TEMP VIEW _admin_bootstrap_ctx AS
SELECT
  lower(current_user()) AS login_identifier,
  lower(current_user()) AS email,
  lower(regexp_extract(current_user(), '^([^@]+)', 1)) AS network_id,
  concat('BOOTSTRAP-', upper(regexp_extract(current_user(), '^([^@]+)', 1))) AS employee_id,
  initcap(replace(regexp_extract(current_user(), '^([^@]+)', 1), '.', ' ')) AS display_name,
  lower(current_user()) AS granted_by;

MERGE INTO sec_role_definition AS target
USING (
  SELECT
    'vendor_admin' AS role_code,
    'Admin' AS role_name,
    'Bootstrap administrator role' AS description,
    3 AS approval_level,
    true AS can_edit,
    true AS can_report,
    true AS can_direct_apply,
    true AS active_flag,
    current_timestamp() AS updated_at,
    granted_by AS updated_by
  FROM _admin_bootstrap_ctx
) AS src
ON target.role_code = src.role_code
WHEN MATCHED THEN
  UPDATE SET
    target.role_name = src.role_name,
    target.description = src.description,
    target.approval_level = src.approval_level,
    target.can_edit = src.can_edit,
    target.can_report = src.can_report,
    target.can_direct_apply = src.can_direct_apply,
    target.active_flag = src.active_flag,
    target.updated_at = src.updated_at,
    target.updated_by = src.updated_by
WHEN NOT MATCHED THEN
  INSERT (
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
  )
  VALUES (
    src.role_code,
    src.role_name,
    src.description,
    src.approval_level,
    src.can_edit,
    src.can_report,
    src.can_direct_apply,
    src.active_flag,
    src.updated_at,
    src.updated_by
  );

MERGE INTO app_employee_directory AS target
USING (
  SELECT
    login_identifier,
    email,
    network_id,
    employee_id,
    split(display_name, ' ')[0] AS first_name,
    CASE
      WHEN size(split(display_name, ' ')) > 1
      THEN concat_ws(' ', slice(split(display_name, ' '), 2, size(split(display_name, ' '))))
      ELSE 'User'
    END AS last_name,
    display_name,
    1 AS active_flag
  FROM _admin_bootstrap_ctx
) AS src
ON lower(target.login_identifier) = lower(src.login_identifier)
WHEN MATCHED THEN
  UPDATE SET
    target.email = src.email,
    target.network_id = src.network_id,
    target.employee_id = src.employee_id,
    target.first_name = src.first_name,
    target.last_name = src.last_name,
    target.display_name = src.display_name,
    target.active_flag = src.active_flag
WHEN NOT MATCHED THEN
  INSERT (
    login_identifier,
    email,
    network_id,
    employee_id,
    manager_id,
    first_name,
    last_name,
    display_name,
    active_flag
  )
  VALUES (
    src.login_identifier,
    src.email,
    src.network_id,
    src.employee_id,
    NULL,
    src.first_name,
    src.last_name,
    src.display_name,
    src.active_flag
  );

MERGE INTO app_user_directory AS target
USING (
  SELECT
    concat('usr-', substr(md5(login_identifier), 1, 12)) AS user_id,
    login_identifier,
    email,
    network_id,
    employee_id,
    split(display_name, ' ')[0] AS first_name,
    CASE
      WHEN size(split(display_name, ' ')) > 1
      THEN concat_ws(' ', slice(split(display_name, ' '), 2, size(split(display_name, ' '))))
      ELSE 'User'
    END AS last_name,
    display_name
  FROM _admin_bootstrap_ctx
) AS src
ON lower(target.login_identifier) = lower(src.login_identifier)
WHEN MATCHED THEN
  UPDATE SET
    target.email = src.email,
    target.network_id = src.network_id,
    target.employee_id = src.employee_id,
    target.first_name = src.first_name,
    target.last_name = src.last_name,
    target.display_name = src.display_name,
    target.active_flag = true,
    target.updated_at = current_timestamp(),
    target.last_seen_at = current_timestamp()
WHEN NOT MATCHED THEN
  INSERT (
    user_id,
    login_identifier,
    email,
    network_id,
    employee_id,
    manager_id,
    first_name,
    last_name,
    display_name,
    active_flag,
    created_at,
    updated_at,
    last_seen_at
  )
  VALUES (
    src.user_id,
    src.login_identifier,
    src.email,
    src.network_id,
    src.employee_id,
    NULL,
    src.first_name,
    src.last_name,
    src.display_name,
    true,
    current_timestamp(),
    current_timestamp(),
    current_timestamp()
  );

MERGE INTO sec_user_role_map AS target
USING (
  SELECT
    u.user_id AS user_principal,
    'vendor_admin' AS role_code,
    true AS active_flag,
    c.granted_by AS granted_by,
    current_timestamp() AS granted_at,
    CAST(NULL AS timestamp) AS revoked_at
  FROM _admin_bootstrap_ctx c
  INNER JOIN app_user_directory u
    ON lower(u.login_identifier) = lower(c.login_identifier)
) AS src
ON target.user_principal = src.user_principal
   AND target.role_code = src.role_code
WHEN MATCHED THEN
  UPDATE SET
    target.active_flag = true,
    target.granted_by = src.granted_by,
    target.granted_at = src.granted_at,
    target.revoked_at = NULL
WHEN NOT MATCHED THEN
  INSERT (
    user_principal,
    role_code,
    active_flag,
    granted_by,
    granted_at,
    revoked_at
  )
  VALUES (
    src.user_principal,
    src.role_code,
    src.active_flag,
    src.granted_by,
    src.granted_at,
    src.revoked_at
  );

SELECT
  u.login_identifier,
  u.user_id,
  r.role_code,
  r.active_flag,
  r.granted_at,
  r.granted_by
FROM app_user_directory u
INNER JOIN sec_user_role_map r
  ON r.user_principal = u.user_id
WHERE lower(u.login_identifier) = lower(current_user())
  AND r.role_code = 'vendor_admin'
ORDER BY r.granted_at DESC;
