USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

DELETE FROM vendor_help_feedback;
DELETE FROM vendor_help_issue;
DELETE FROM vendor_help_article;

INSERT INTO vendor_help_article
  (article_id, slug, title, section, article_type, role_visibility, content_md, owned_by, updated_at, updated_by, created_at, created_by)
VALUES
  (
    'help-001',
    'quick-start',
    'Quick Start',
    'Quick Start',
    'workflow',
    'viewer,editor,admin',
    '## Scenario\nCreate and navigate a full vendor lifecycle in one session.\n\n## Steps\n1. Create a vendor\n2. Add an offering\n3. Create a project\n4. Link vendor + offering to the project\n5. Add a demo and document link\n\n## Checkpoints\n- Vendor, offering, project appear in lists\n- Demo and doc links render correctly',
    'Product Ops',
    current_timestamp(),
    'seed:system',
    current_timestamp(),
    'seed:system'
  ),
  (
    'help-002',
    'vendor-360-overview',
    'Find a vendor and read Vendor 360',
    'Core Workflows',
    'workflow',
    'viewer,editor,admin',
    '## Scenario\nAnswer vendor status and ownership questions quickly.\n\n## Steps\n1. Open Vendor 360\n2. Search by vendor name\n3. Review ownership, contracts, demos, and docs\n4. Confirm audit trail in Changes',
    'Vendor Stewardship',
    current_timestamp(),
    'seed:system',
    current_timestamp(),
    'seed:system'
  ),
  (
    'help-003',
    'create-project',
    'Create and manage a project',
    'Projects',
    'workflow',
    'editor,admin',
    '## Scenario\nStand up a project and track delivery artifacts.\n\n## Steps\n1. Create project\n2. Map vendor and offering\n3. Add demo and note\n4. Add docs\n5. Review activity stream',
    'PMO',
    current_timestamp(),
    'seed:system',
    current_timestamp(),
    'seed:system'
  );

INSERT INTO vendor_help_feedback
  (feedback_id, article_id, article_slug, was_helpful, comment, user_principal, page_path, created_at)
VALUES
  ('hfb-001', 'help-001', 'quick-start', true, 'Clear and complete.', 'dev_admin@example.com', '/help/quick-start', current_timestamp());

INSERT INTO vendor_help_issue
  (issue_id, article_id, article_slug, issue_title, issue_description, page_path, user_principal, created_at)
VALUES
  ('his-001', 'help-002', 'vendor-360-overview', 'Add screenshot refresh', 'Screenshots should show latest nav labels.', '/help/vendor-360-overview', 'editor@example.com', current_timestamp());