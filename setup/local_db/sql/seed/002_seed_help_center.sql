PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

DELETE FROM vendor_help_feedback;
DELETE FROM vendor_help_issue;
DELETE FROM vendor_help_article;

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-001',
  'quick-start',
  'Quick Start',
  'Quick Start',
  'workflow',
  'viewer,editor,admin',
  '## Scenario\nYou need to stand up a full vendor record from scratch.\n\n## Navigate\n- Vendor 360: /vendors\n- Projects: /projects\n- Demos: /demos\n\n![Vendor 360 list with New Vendor button](/static/help/screenshots/vendor-360-list.png)\n\n## Steps\n1. Create a vendor. See [Add a new vendor](/help/add-vendor).\n2. Add an offering. See [Add an offering](/help/add-offering).\n3. Create a project. See [Create a project](/help/create-project).\n4. Link vendors and offerings. See [Link vendors and offerings](/help/link-vendors-offerings-to-project).\n5. Add a demo to the project. See [Add a demo to a project](/help/add-project-demo).\n6. Add a document link. See [Add a document link](/help/add-document-link).\n\n## Checkpoints\n- Vendor, offering, and project show up in lists.\n- Demo appears under the project.\n- Document link opens correctly.\n\n## Troubleshooting\n- New Vendor not visible: you are in view only. Request Editor access.\n- Create Vendor fails: Legal Name and Line of Business are required.\n- Add Link fails: URL must start with http or https.\n\n## Role tips\nViewer: read only.\nEditor: can create and edit.\nAdmin: can edit and manage permissions.',
  'Product Ops',
  '2026-02-10 09:00:00',
  'seed:system',
  '2026-02-10 09:00:00',
  'seed:system'
);

INSERT INTO vendor_help_feedback (
  feedback_id,
  article_id,
  article_slug,
  was_helpful,
  comment,
  user_principal,
  page_path,
  created_at
) VALUES (
  'hfb-001',
  'help-001',
  'quick-start',
  1,
  'Helpful walkthrough for onboarding.',
  'viewer@example.com',
  '/help/quick-start',
  '2026-02-10 10:00:00'
);

INSERT INTO vendor_help_issue (
  issue_id,
  article_id,
  article_slug,
  issue_title,
  issue_description,
  page_path,
  user_principal,
  created_at
) VALUES (
  'his-001',
  'help-001',
  'quick-start',
  'Need refresh for screenshot labels',
  'Navigation labels changed in latest UI update.',
  '/help/quick-start',
  'editor@example.com',
  '2026-02-10 10:05:00'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-002',
  'vendor-360-overview',
  'Find a vendor and read Vendor 360',
  'Core Workflows',
  'workflow',
  'viewer,editor,admin',
  '## Scenario\nYou need to answer vendor status questions in a meeting.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Vendor detail summary cards](/static/help/screenshots/vendor-detail-summary.png)\n\n## Steps\n1. Open Vendor 360 and search by vendor name or id.\n2. Select the vendor row.\n3. Review Summary cards for Lifecycle, Risk Tier, Offerings, and Demos.\n4. Use sections for Ownership, Contracts, Demos, Documents, and Changes.\n5. Use Show Raw Fields when you need source values.\n\n## Checkpoints\n- You can describe lifecycle and risk.\n- You can name the primary owner and last change.\n\n## Troubleshooting\n- Vendor missing: clear filters and search by Legal Name.\n- View only: request Editor access.\n- Sections empty: confirm data exists for that vendor.\n\n## Role tips\nViewer: read only.\nEditor: can add contacts and document links.\nAdmin: can manage permissions and audits.',
  'Vendor Stewardship',
  '2026-02-10 09:05:00',
  'seed:system',
  '2026-02-10 09:05:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-003',
  'add-vendor',
  'Add a new vendor',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou onboard a new vendor for a project kickoff.\n\n## Navigate\n- Vendor 360: /vendors\n- Create vendor: /vendors/new\n\n![Vendor 360 list with New Vendor button](/static/help/screenshots/vendor-360-list.png)\n\n## Steps\n1. Open Vendor 360 and select New Vendor.\n2. Enter Legal Name and Display Name.\n3. Select Lifecycle State.\n4. Select Line of Business or choose Add new line of business.\n5. Select Create Vendor.\n\n## Checkpoints\n- Vendor appears in the list.\n- Summary tab opens for the new vendor.\n\n## Next actions\n- Add an offering in Offerings.\n- Add owners and contacts in Ownership.\n\n## Troubleshooting\n- New Vendor not visible: you are in view only. Request Editor access.\n- Line of Business missing: choose Add new line of business and enter value.\n- Validation error: required fields are Legal Name and Line of Business.\n\n## Role tips\nViewer: cannot create.\nEditor: can create and submit edits.\nAdmin: can create and manage permissions.',
  'Vendor Stewardship',
  '2026-02-10 09:10:00',
  'seed:system',
  '2026-02-10 09:10:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-004',
  'add-offering',
  'Add an offering to a vendor',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need to capture a new product under an existing vendor.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Vendor detail with Offerings tab](/static/help/screenshots/vendor-detail-offerings.png)\n\n## Steps\n1. Open Vendor 360 and select the vendor.\n2. Open Offerings and select New Offering.\n3. Enter Offering Name.\n4. Select Offering Type and Lifecycle State.\n5. Select Create Offering.\n\n## Checkpoints\n- Offering appears in the Offerings list.\n- Counts for contracts, demos, and docs start at zero.\n\n## Next actions\n- Add offering owners and contacts.\n- Map contracts or demos to this offering.\n\n## Troubleshooting\n- Offering Type list is empty: ask an Admin to add lookup values in Admin.\n- Create Offering fails: Offering Name is required.\n\n## Role tips\nViewer: cannot create.\nEditor: can create and submit edits.\nAdmin: can create and manage defaults.',
  'Offerings',
  '2026-02-10 09:12:00',
  'seed:system',
  '2026-02-10 09:12:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-005',
  'edit-vendor-details',
  'Edit vendor details and see audit history',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need to add a new owner and capture a reason.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Vendor Ownership section](/static/help/screenshots/vendor-ownership-section.png)\n\n## Steps\n1. Open Vendor 360 and select the vendor.\n2. Open Ownership.\n3. Add an Owner, Org Assignment, or Contact.\n4. Enter a Reason for the change.\n5. Select Add or Save.\n6. Open Changes to review the audit entry.\n\n## Checkpoints\n- New owner or contact appears.\n- Change entry appears in Changes.\n\n## Troubleshooting\n- Save does nothing: Reason is required.\n- Pending change request: your role needs approval.\n\n## Role tips\nViewer: read only.\nEditor: can submit change requests.\nAdmin: can apply changes directly and manage access.',
  'Vendor Stewardship',
  '2026-02-10 09:15:00',
  'seed:system',
  '2026-02-10 09:15:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-006',
  'offerings-list-and-mappings',
  'Use the Offerings list and mappings',
  'Core Workflows',
  'workflow',
  'viewer,editor,admin',
  '## Scenario\nYou need to map unassigned contracts and demos to an offering.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Offerings list with Unassigned sections](/static/help/screenshots/vendor-offerings-unassigned.png)\n\n## Steps\n1. Open a vendor and open Offerings.\n2. Review offering rows for lifecycle, owners, and counts.\n3. Scroll to Unassigned Contracts or Unassigned Demos.\n4. Select a target offering.\n5. Enter a Reason.\n6. Select Map or Map Selected.\n\n## Checkpoints\n- Items move into the selected offering.\n- Reason appears in Changes.\n\n## Troubleshooting\n- Map Selected disabled: select at least one row.\n- Mapping fails: Reason is required.\n- Item missing: check status filters or inactive records.\n\n## Role tips\nViewer: cannot map.\nEditor: can map with a reason.\nAdmin: can map and manage defaults.',
  'Offerings',
  '2026-02-10 09:20:00',
  'seed:system',
  '2026-02-10 09:20:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-007',
  'edit-offering-details',
  'Edit offering details',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need to change lifecycle state after approval.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Offering Profile edit form](/static/help/screenshots/offering-profile-edit.png)\n\n## Steps\n1. Open the vendor and select the offering.\n2. Open Profile.\n3. Update name, type, or lifecycle.\n4. Enter a Reason.\n5. Select Save.\n\n## Checkpoints\n- Updated values appear in the profile.\n- Change entry appears in Changes.\n\n## Troubleshooting\n- Save fails: Reason is required.\n- View only: request Editor access.\n\n## Role tips\nViewer: read only.\nEditor: can submit updates.\nAdmin: can apply updates directly.',
  'Offerings',
  '2026-02-10 09:22:00',
  'seed:system',
  '2026-02-10 09:22:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-008',
  'create-project',
  'Create a project',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need a project to track an implementation.\n\n## Navigate\n- Projects list: /projects\n\n![Projects page with Create Project button](/static/help/screenshots/project-list-view.png)\n\n## Steps\n1. Open Projects and select Create Project.\n2. Enter Project Name, Type, Status, and Owner Principal.\n3. Optional: link vendors and offerings.\n4. Select Create Project.\n\n## Checkpoints\n- Project appears in Projects list.\n- Project Detail opens.\n\n## Next actions\n- Link vendors and offerings.\n- Add a demo and documents.\n\n## Troubleshooting\n- Owner Principal not found: use a valid directory email.\n- Save fails: Project Name is required.\n\n## Role tips\nViewer: read only.\nEditor: can create and edit.\nAdmin: can manage permissions.',
  'Projects',
  '2026-02-10 09:25:00',
  'seed:system',
  '2026-02-10 09:25:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-009',
  'edit-project',
  'Edit a project',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need to change status and dates after kickoff.\n\n## Navigate\n- Projects list: /projects\n\n![Project edit form](/static/help/screenshots/project-edit-form.png)\n\n## Steps\n1. Open the project.\n2. Select Edit Project.\n3. Update status, dates, or linked vendors and offerings.\n4. Enter a Reason.\n5. Select Save Project.\n\n## Checkpoints\n- Updated fields display on Project Detail.\n- Change entry appears in Changes.\n\n## Troubleshooting\n- Save fails: Reason is required.\n- Linked vendor not found: use the search picker and select a result.\n\n## Role tips\nViewer: cannot edit.\nEditor: can edit with reason.\nAdmin: can edit and manage roles.',
  'Projects',
  '2026-02-10 09:28:00',
  'seed:system',
  '2026-02-10 09:28:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-010',
  'project-detail',
  'Read a project detail page',
  'Core Workflows',
  'workflow',
  'viewer,editor,admin',
  '## Scenario\nYou are reviewing project health before a status meeting.\n\n## Navigate\n- Projects list: /projects\n\n![Project Detail summary cards](/static/help/screenshots/project-detail-summary.png)\n\n## Steps\n1. Open Projects and select a project row.\n2. Review Summary cards for Status, Type, and Linked Offerings.\n3. Review Linked Offerings and Demos sections.\n4. Review Documents for project links.\n\n## Checkpoints\n- You can describe scope, linked vendors, and demo status.\n\n## Troubleshooting\n- Project does not open: clear filters and search again.\n- Linked offerings empty: link them in Edit Project.\n\n## Role tips\nViewer: read only.\nEditor: can add demos and documents.\nAdmin: can manage access.',
  'Projects',
  '2026-02-10 09:30:00',
  'seed:system',
  '2026-02-10 09:30:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-011',
  'add-project-demo',
  'Add a demo to a project',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou want to capture a scheduled demo for a project.\n\n## Navigate\n- Projects list: /projects\n\n![Project Demos section with Add Demo](/static/help/screenshots/project-demos-section.png)\n\n## Steps\n1. Open the project.\n2. In Demos, select Add Demo.\n3. Enter Demo Name and dates.\n4. Select Outcome and Score when available.\n5. Optional: link an offering.\n6. Select Create Demo.\n\n## Checkpoints\n- Demo appears in the project demo table.\n\n## Troubleshooting\n- Create Demo fails: Demo Name is required.\n- Offering list empty: vendor has no offerings yet.\n\n## Role tips\nViewer: cannot add demos.\nEditor: can add demos.\nAdmin: can add demos and manage audits.',
  'Projects',
  '2026-02-10 09:32:00',
  'seed:system',
  '2026-02-10 09:32:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-012',
  'link-vendors-offerings-to-project',
  'Link vendors and offerings to a project',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need the project to roll up spend and demo data.\n\n## Navigate\n- Projects list: /projects\n\n![Edit Project linked vendors and offerings](/static/help/screenshots/project-linked-vendors.png)\n\n## Steps\n1. Open the project and select Edit Project.\n2. In Linked Vendors, search and select a vendor.\n3. In Linked Offerings, search and select offerings.\n4. Enter a Reason.\n5. Select Save Project.\n\n## Checkpoints\n- Linked vendors and offerings display on Project Detail.\n\n## Troubleshooting\n- Search results empty: check spelling or use vendor id.\n- Save fails: Reason is required.\n\n## Role tips\nViewer: cannot link.\nEditor: can link.\nAdmin: can link and manage roles.',
  'Projects',
  '2026-02-10 09:35:00',
  'seed:system',
  '2026-02-10 09:35:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-013',
  'add-document-link',
  'Add a document link',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need to attach a security review or contract doc.\n\n## Navigate\n- Vendor 360: /vendors\n- Projects: /projects\n\n![Documents section with Add Link](/static/help/screenshots/documents-add-link.png)\n\n## Steps\n1. Open a vendor, offering, or project page.\n2. Find Documents.\n3. Select Add Link.\n4. Enter Title, URL, Source, and Owner.\n5. Select Add Link.\n\n## Checkpoints\n- Link appears in Documents table.\n- Link opens in a new tab.\n\n## Troubleshooting\n- Add Link fails: URL must start with http or https.\n- Owner not found: use a directory email.\n\n## Role tips\nViewer: can view only.\nEditor: can add links.\nAdmin: can add and remove links.',
  'Documents',
  '2026-02-10 09:38:00',
  'seed:system',
  '2026-02-10 09:38:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-014',
  'update-mappings',
  'Update mappings for a vendor or offering',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou need to correct a mapping after new data arrives.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Unassigned items mapping panel](/static/help/screenshots/vendor-offerings-unassigned.png)\n\n## Steps\n1. Open the vendor and select Offerings.\n2. Scroll to Unassigned Contracts or Unassigned Demos.\n3. Select a target offering.\n4. Enter a Reason.\n5. Select Map or Map Selected.\n\n## Checkpoints\n- Items appear under the target offering.\n- Change appears in Changes.\n\n## Troubleshooting\n- Map fails: Reason is required.\n- Item missing: check contract status or filters.\n\n## Role tips\nViewer: cannot map.\nEditor: can map with reason.\nAdmin: can map and update defaults.',
  'Offerings',
  '2026-02-10 09:40:00',
  'seed:system',
  '2026-02-10 09:40:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-015',
  'fix-data-mismatch',
  'Fix a data mismatch without losing audit history',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou see a value that is incorrect but need audit history preserved.\n\n## Navigate\n- Vendor 360: /vendors\n\n![Edit form with Reason field](/static/help/screenshots/vendor-edit-form.png)\n\n## Steps\n1. Open the vendor or offering record.\n2. Update the field in the edit form.\n3. Enter a Reason that explains the mismatch.\n4. Save the change.\n5. Review Changes for the audit entry.\n\n## Checkpoints\n- Corrected value appears.\n- Audit entry shows old and new values.\n\n## Troubleshooting\n- Pending change request: wait for approval if you are not a direct apply role.\n- Value reverts: source refresh may overwrite. Add a note in Changes and notify the data owner.\n\n## Role tips\nViewer: cannot change data.\nEditor: can submit change requests.\nAdmin: can apply changes directly.',
  'Data Quality',
  '2026-02-10 09:42:00',
  'seed:system',
  '2026-02-10 09:42:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-016',
  'demo-outcomes-overview',
  'Track demo outcomes',
  'Core Workflows',
  'guide',
  'viewer,editor,admin',
  '## Scenario\nYou need a consolidated list of demo outcomes.\n\n## Navigate\n- Demo Outcomes: /demos\n\n![Demo Outcomes filters](/static/help/screenshots/demo-catalog-list.png)\n\n## Steps\n1. Open Demos.\n2. Use Search and Outcome filters.\n3. Review stage, score, and outcome.\n4. If you have edit access, add a demo outcome.\n\n### Add a demo outcome\n1. Enter Vendor ID and Offering ID.\n2. Set Demo Date and Overall Score.\n3. Select Selection Outcome.\n4. Add Notes.\n5. Select Save Demo Outcome.\n\n## Checkpoints\n- New row appears in the list.\n- Stage shows Scheduled.\n\n## Troubleshooting\n- Add Demo Outcome hidden: you need Editor access.\n- Non selection reason required for not_selected.\n\n## Role tips\nViewer: read only.\nEditor: can add outcomes.\nAdmin: can edit and audit.',
  'Demos',
  '2026-02-10 09:45:00',
  'seed:system',
  '2026-02-10 09:45:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-017',
  'demo-workspace',
  'Use a demo workspace',
  'Core Workflows',
  'workflow',
  'editor,admin',
  '## Scenario\nYou run a demo review and update stage history.\n\n## Navigate\n- Demos: /demos\n\n![Demo workspace header and stage history](/static/help/screenshots/demo-workspace-stage.png)\n\n## Steps\n1. Open a demo from Demos.\n2. Review current Stage and Outcome.\n3. Select a new Stage and enter Notes.\n4. Select Update Stage.\n5. Review scorecards and summary.\n\n## Checkpoints\n- Stage history shows new entry.\n- Summary reflects latest stage.\n\n## Troubleshooting\n- Update Stage fails: Notes are required.\n- Review form empty: no scorecards submitted yet.\n\n## Role tips\nViewer: read only.\nEditor: can update stage.\nAdmin: can update and audit.',
  'Demos',
  '2026-02-10 09:48:00',
  'seed:system',
  '2026-02-10 09:48:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-018',
  'vendor-360-faq',
  'Vendor 360 FAQ',
  'FAQs',
  'faq',
  'viewer,editor,admin',
  '## Questions\n\n**Why does a vendor show as retired?**\nRetired vendors are no longer active but remain for history.\n\n**What is Risk Tier?**\nRisk Tier indicates vendor risk level: low, medium, or high.\n\n**Why is Line of Business blank?**\nLOB is missing. Ask an Editor to update it in Ownership.\n\n**Where do contracts show up?**\nOpen the vendor record and review Contracts.\n\n**What is Show Raw Fields?**\nIt displays source system values for audit and support.\n\n**How do I add a vendor?**\nSee [Add a new vendor](/help/add-vendor).\n\n**How do I add an offering?**\nSee [Add an offering](/help/add-offering).',
  'Vendor Stewardship',
  '2026-02-10 09:50:00',
  'seed:system',
  '2026-02-10 09:50:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-019',
  'offerings-faq',
  'Offerings FAQ',
  'FAQs',
  'faq',
  'viewer,editor,admin',
  '## Questions\n\n**What is an offering?**\nAn offering is a product or service a vendor provides.\n\n**Why is an offering in review?**\nLifecycle is in_review while it is approved.\n\n**How do I add an offering?**\nSee [Add an offering](/help/add-offering).\n\n**How do I map a contract to an offering?**\nUse Unassigned Contracts in Offerings and select Map. See [Update mappings](/help/update-mappings).\n\n**Why is the offering type list empty?**\nDefaults are missing. Ask an Admin to add lookup values in /admin?section=defaults.\n\n**Can I delete an offering?**\nOfferings are retired, not deleted, to keep history.',
  'Offerings',
  '2026-02-10 09:52:00',
  'seed:system',
  '2026-02-10 09:52:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-020',
  'projects-faq',
  'Projects FAQ',
  'FAQs',
  'faq',
  'viewer,editor,admin',
  '## Questions\n\n**Can I create a project without a vendor?**\nYes. Link vendors later.\n\n**Why is a project blocked?**\nStatus is blocked. Edit the project to update it.\n\n**How do I add a demo?**\nOpen the project and select Add Demo. See [Add a demo to a project](/help/add-project-demo).\n\n**Why is a project missing in the list?**\nClear filters or search by name or id.\n\n**What is a linked offering?**\nAn offering tied to the project work. See [Link vendors and offerings](/help/link-vendors-offerings-to-project).',
  'Projects',
  '2026-02-10 09:54:00',
  'seed:system',
  '2026-02-10 09:54:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-021',
  'documents-faq',
  'Documents FAQ',
  'FAQs',
  'faq',
  'viewer,editor,admin',
  '## Questions\n\n**Do we upload files?**\nNo. Use links only.\n\n**What sources are allowed?**\nSharePoint, Confluence, GitHub, or other approved URLs.\n\n**Why is my link not saving?**\nThe URL must start with http or https.\n\n**Can I remove a link?**\nEditors and Admins can remove links.\n\n**Who owns a document link?**\nOwner indicates who maintains the link.\n\n**How do I add a link?**\nSee [Add a document link](/help/add-document-link).',
  'Documents',
  '2026-02-10 09:55:00',
  'seed:system',
  '2026-02-10 09:55:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-022',
  'admin-faq',
  'Admin FAQ',
  'FAQs',
  'faq',
  'admin',
  '## Questions\n\n**How do I grant a role?**\nOpen /admin?section=access and use Grant Role.\n\n**What is a role override?**\nIn dev mode, Admins can test other roles with the role switcher.\n\n**Can I delete a lookup value?**\nUse Remove in /admin?section=defaults to hide it and keep history.\n\n**Where are audit logs?**\nUse Changes in vendor or offering records and workflow queues.\n\n**Where do I manage LOB scope?**\nUse Line of Business Scope Grants in /admin?section=access.',
  'Admin Guide',
  '2026-02-10 09:56:00',
  'seed:system',
  '2026-02-10 09:56:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-023',
  'troubleshooting-common-issues',
  'Troubleshooting common issues',
  'Troubleshooting',
  'troubleshooting',
  'viewer,editor,admin',
  '## Symptoms and fixes\n\n**I cannot edit this field.**\nYou are in view only. Request Editor access.\n\n**Vendor does not show up.**\nClear filters and search by Legal Name or id.\n\n**Offering mapping will not save.**\nAdd a Reason and select Map again.\n\n**My project demo disappeared.**\nCheck if it was removed and review Changes.\n\n**Document link is not opening.**\nVerify the URL starts with http or https.\n\n**Owner field is blank.**\nAdd owner in Ownership and save with a Reason.\n\n**I see Pending change request.**\nWait for an approver or ask an Admin to apply the change.\n\n**Search returns nothing.**\nTry fewer words or use vendor id.\n\n**Login shows no role.**\nRequest access on /access/request.\n\n## If still blocked\nCapture the URL, the action you took, and the error message, then open a Help issue from the page.',
  'Support',
  '2026-02-10 10:00:00',
  'seed:system',
  '2026-02-10 10:00:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-024',
  'glossary',
  'Glossary',
  'Glossary',
  'reference',
  'viewer,editor,admin',
  '## Terms\n\n**Vendor**\nA company that provides products or services.\n\n**Offering**\nA product or service from a vendor.\n\n**Mapping**\nA link that connects records, like a contract to an offering.\n\n**Project**\nA work item that tracks goals, demos, and links to vendors.\n\n**Demo**\nA product review meeting with a score and outcome.\n\n**Lifecycle State**\nThe status of a vendor or offering, such as draft, active, or retired.\n\n**Line of Business (LOB)**\nThe internal business line that owns the vendor relationship.\n\n**Lookup**\nA fixed list of values used in forms.\n\n**Reason**\nA required explanation for changes to keep audit history.\n\n**Audit Log**\nA history of changes with who and when.',
  'Product Ops',
  '2026-02-10 10:02:00',
  'seed:system',
  '2026-02-10 10:02:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-025',
  'admin-portal-overview',
  'Admin portal overview',
  'Admin Guide',
  'guide',
  'admin',
  '## Scenario\nYou need to manage roles and lookup defaults.\n\n## Navigate\n- Admin Portal: /admin\n- Roles and Users: /admin?section=access\n- Defaults: /admin?section=defaults\n\n![Admin Portal tabs for Roles and Users, Defaults](/static/help/screenshots/admin-defaults-catalog.png)\n\n## What this page does\nAdmin Portal manages role access and lookup defaults used across forms.\n\n## Common actions\n- Grant or revoke roles.\n- Update lookup labels and sort order.\n- Manage group role grants and LOB scope.\n\n## Role tips\nOnly Admin roles can open this page.',
  'Admin Team',
  '2026-02-10 10:05:00',
  'seed:system',
  '2026-02-10 10:05:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-026',
  'admin-manage-lookups',
  'Add or edit lookup values safely',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nYou need to add a new offering type used in forms.\n\n## Navigate\n- Defaults: /admin?section=defaults\n\n![Defaults Catalog and option table](/static/help/screenshots/admin-section-defaults.png)\n\n## Steps\n1. Open Admin Portal and select Defaults.\n2. Choose a Category and Status.\n3. Update Label, Sort, and Valid dates.\n4. Select Save to apply.\n5. Use Remove to hide a value without deleting history.\n\n## Checkpoints\n- The option appears in the Defaults table.\n- Forms show the new value.\n\n## Troubleshooting\n- Value does not show: check valid dates and status filter.\n- Duplicate label: set the older value to historical.\n\n## Role tips\nOnly Admins can manage lookups.',
  'Admin Team',
  '2026-02-10 10:07:00',
  'seed:system',
  '2026-02-10 10:07:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-027',
  'admin-manage-permissions',
  'Manage user permissions',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nYou need to grant Editor access for a new contributor.\n\n## Navigate\n- Roles and Users: /admin?section=access\n\n![Role Grants table and Grant Role form](/static/help/screenshots/admin-access-roles.png)\n\n## Steps\n1. Open Admin Portal and select Roles and Users.\n2. In Role Grants, enter User Principal.\n3. Choose a Role and select Grant Role.\n4. Use Change or Revoke to update access later.\n\n## Checkpoints\n- User appears in Role Grants with active flag.\n\n## Troubleshooting\n- User not found: confirm email and directory entry.\n- Role not available: define it in Role Catalog first.\n\n## Role tips\nOnly Admins can grant roles.',
  'Admin Team',
  '2026-02-10 10:09:00',
  'seed:system',
  '2026-02-10 10:09:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-028',
  'admin-audit-logs',
  'View audit logs',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nYou need audit evidence for a vendor change.\n\n## Navigate\n- Vendor 360: /vendors\n- Workflows: /workflows/pending-approvals\n\n![Changes section in vendor detail](/static/help/screenshots/vendor-changes-section.png)\n\n## Steps\n1. Open the vendor or offering record.\n2. Select Changes.\n3. Review Change Requests and audit entries.\n4. If a change is pending, review it in workflows.\n\n## Checkpoints\n- You can identify who changed data and when.\n\n## Troubleshooting\n- Changes empty: the record has no edits yet.\n- Missing data: confirm the record id and filters.\n\n## Role tips\nOnly Admins can manage audit workflows.',
  'Admin Team',
  '2026-02-10 10:11:00',
  'seed:system',
  '2026-02-10 10:11:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-029',
  'admin-refresh-status',
  'Check refresh status and schedules',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nYou need to confirm data freshness after a source update.\n\n## Navigate\n- Admin Portal: /admin\n\n[Screenshot: Data freshness panel or status widget]\n\n## Steps\n1. Open Admin Portal.\n2. Review any data freshness indicators if available.\n3. If there is no panel, confirm latest data via reports.\n\n## Checkpoints\n- You can state when the last refresh occurred.\n\n## Troubleshooting\n- Status missing: confirm the refresh job is configured.\n- Status failed: coordinate with the ingestion owner.\n\n## Role tips\nOnly Admins can manage refresh jobs.',
  'Admin Team',
  '2026-02-10 10:13:00',
  'seed:system',
  '2026-02-10 10:13:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-030',
  'admin-manage-source-mappings',
  'Manage source mappings',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nA source id changed and the record needs a mapping update.\n\n## Navigate\n- Vendor 360: /vendors\n\n[Screenshot: Vendor Changes section with change requests]\n\n## Steps\n1. Identify the source system and record id.\n2. Open the vendor or offering record.\n3. Submit a change request with the new mapping values.\n4. Approve and apply the change.\n\n## Checkpoints\n- Record links to the correct source id.\n\n## Troubleshooting\n- Mapping still wrong: a later refresh may overwrite it. Coordinate with data owners.\n- Change request stuck: ensure approvers have access.\n\n## Role tips\nOnly Admins can manage source mappings.',
  'Admin Team',
  '2026-02-10 10:15:00',
  'seed:system',
  '2026-02-10 10:15:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-031',
  'admin-deactivate-vs-delete',
  'Deactivate vs delete rules',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nA stakeholder asks to delete a record that should remain for audit.\n\n## Navigate\n- Defaults: /admin?section=defaults\n\n[Screenshot: Remove action in Defaults]\n\n## Steps\n1. Prefer deactivate to keep audit history.\n2. Use Remove in Defaults to hide values.\n3. Set lifecycle state to retired for vendors or offerings.\n\n## Checkpoints\n- Record is hidden from active lists.\n- History remains for reporting.\n\n## Troubleshooting\n- Value still visible: check active status and valid dates.\n\n## Role tips\nOnly Admins can change deletion rules.',
  'Admin Team',
  '2026-02-10 10:17:00',
  'seed:system',
  '2026-02-10 10:17:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-032',
  'admin-access-requests',
  'Manage access requests',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nA user requests access for a new project.\n\n## Navigate\n- Roles and Users: /admin?section=access\n\n[Screenshot: Role Grants and Line of Business Scope Grants]\n\n## Steps\n1. Open Admin Portal and select Roles and Users.\n2. Review Role Grants for the user.\n3. Grant the correct role.\n4. Add LOB Scope if needed.\n\n## Checkpoints\n- User has the correct role and scope.\n\n## Troubleshooting\n- User still has no role: confirm the grant is active.\n- Wrong role granted: use Change to correct it.\n\n## Role tips\nOnly Admins can manage access.',
  'Admin Team',
  '2026-02-10 10:19:00',
  'seed:system',
  '2026-02-10 10:19:00',
  'seed:system'
);

INSERT INTO vendor_help_article (
  article_id,
  slug,
  title,
  section,
  article_type,
  role_visibility,
  content_md,
  owned_by,
  updated_at,
  updated_by,
  created_at,
  created_by
) VALUES (
  'help-033',
  'admin-role-definitions',
  'Define roles and permissions',
  'Admin Guide',
  'workflow',
  'admin',
  '## Scenario\nYou need a new role for a limited contributor.\n\n## Navigate\n- Roles and Users: /admin?section=access\n\n[Screenshot: Role Catalog and Create or Update Role]\n\n## Steps\n1. Open Admin Portal and select Roles and Users.\n2. Review Role Catalog for current roles.\n3. In Create or Update Role, enter Role Code and Name.\n4. Select approval level and permissions.\n5. Select Save Role.\n\n## Checkpoints\n- Role appears in Role Catalog.\n- Role is available for grants.\n\n## Troubleshooting\n- Role code exists: update it instead of creating.\n- Users cannot edit: ensure can_edit is enabled.\n\n## Role tips\nOnly Admins can define roles.',
  'Admin Team',
  '2026-02-10 10:21:00',
  'seed:system',
  '2026-02-10 10:21:00',
  'seed:system'
);

COMMIT;
