PRAGMA foreign_keys = ON;

-- Transitional compatibility bridge for Wave 1 parity.
-- Goal: keep current application functionality available while canonical V1 model is completed.

CREATE TABLE IF NOT EXISTS app_user_directory (
  user_id TEXT PRIMARY KEY,
  login_identifier TEXT NOT NULL UNIQUE,
  email TEXT,
  network_id TEXT,
  employee_id TEXT,
  manager_id TEXT,
  first_name TEXT,
  last_name TEXT,
  display_name TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_user_settings (
  setting_id TEXT PRIMARY KEY,
  user_principal TEXT NOT NULL,
  setting_key TEXT NOT NULL,
  setting_value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (user_principal) REFERENCES app_user_directory(login_identifier),
  UNIQUE (user_principal, setting_key)
);

CREATE TABLE IF NOT EXISTS app_usage_log (
  usage_event_id TEXT PRIMARY KEY,
  user_principal TEXT NOT NULL,
  page_name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sec_role_definition (
  role_code TEXT PRIMARY KEY,
  role_name TEXT NOT NULL,
  description TEXT,
  approval_level INTEGER NOT NULL DEFAULT 0,
  can_edit INTEGER NOT NULL DEFAULT 0 CHECK (can_edit IN (0, 1)),
  can_report INTEGER NOT NULL DEFAULT 0 CHECK (can_report IN (0, 1)),
  can_direct_apply INTEGER NOT NULL DEFAULT 0 CHECK (can_direct_apply IN (0, 1)),
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sec_role_permission (
  role_code TEXT NOT NULL,
  object_name TEXT NOT NULL,
  action_code TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  updated_at TEXT NOT NULL,
  FOREIGN KEY (role_code) REFERENCES sec_role_definition(role_code),
  UNIQUE (role_code, object_name, action_code)
);

CREATE TABLE IF NOT EXISTS sec_user_role_map (
  user_principal TEXT NOT NULL,
  role_code TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  granted_by TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY (role_code) REFERENCES sec_role_definition(role_code),
  CHECK ((active_flag = 1 AND revoked_at IS NULL) OR active_flag = 0),
  UNIQUE (user_principal, role_code, active_flag)
);

CREATE TABLE IF NOT EXISTS sec_group_role_map (
  group_principal TEXT NOT NULL,
  role_code TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  granted_by TEXT NOT NULL,
  granted_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY (role_code) REFERENCES sec_role_definition(role_code),
  CHECK ((active_flag = 1 AND revoked_at IS NULL) OR active_flag = 0),
  UNIQUE (group_principal, role_code, active_flag)
);

CREATE TABLE IF NOT EXISTS sec_user_org_scope (
  user_principal TEXT NOT NULL,
  org_id TEXT NOT NULL,
  scope_level TEXT NOT NULL,
  active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
  granted_at TEXT NOT NULL,
  UNIQUE (user_principal, org_id, scope_level, active_flag)
);

CREATE TABLE IF NOT EXISTS audit_entity_change (
  change_event_id TEXT PRIMARY KEY,
  entity_name TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  actor_user_principal TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  request_id TEXT,
  FOREIGN KEY (request_id) REFERENCES change_request(request_id)
);

CREATE TABLE IF NOT EXISTS audit_workflow_event (
  workflow_event_id TEXT PRIMARY KEY,
  workflow_type TEXT NOT NULL,
  workflow_id TEXT NOT NULL,
  old_status TEXT,
  new_status TEXT,
  actor_user_principal TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS audit_access_event (
  access_event_id TEXT PRIMARY KEY,
  actor_user_principal TEXT NOT NULL,
  action_type TEXT NOT NULL,
  target_user_principal TEXT,
  target_role TEXT,
  event_ts TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (target_role) REFERENCES sec_role_definition(role_code)
);

CREATE TABLE IF NOT EXISTS vendor_help_article (
  article_id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  section TEXT NOT NULL,
  article_type TEXT NOT NULL,
  role_visibility TEXT NOT NULL,
  content_md TEXT NOT NULL,
  owned_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendor_help_feedback (
  feedback_id TEXT PRIMARY KEY,
  article_id TEXT,
  article_slug TEXT,
  was_helpful INTEGER NOT NULL DEFAULT 0 CHECK (was_helpful IN (0, 1)),
  comment TEXT,
  user_principal TEXT,
  page_path TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (article_id) REFERENCES vendor_help_article(article_id),
  FOREIGN KEY (article_slug) REFERENCES vendor_help_article(slug)
);

CREATE TABLE IF NOT EXISTS vendor_help_issue (
  issue_id TEXT PRIMARY KEY,
  article_id TEXT,
  article_slug TEXT,
  issue_title TEXT NOT NULL,
  issue_description TEXT NOT NULL,
  page_path TEXT,
  user_principal TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (article_id) REFERENCES vendor_help_article(article_id),
  FOREIGN KEY (article_slug) REFERENCES vendor_help_article(slug)
);
