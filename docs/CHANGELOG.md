# Changelog

## 2026-02-09T21:48:09Z | VC-20260209-214809-5452
- Added a centralized application SQL catalog under `app/vendor_catalog_app/sql/` with domain folders for:
  - `ingestion/`
  - `inserts/`
  - `updates/`
  - `reporting/`
- Added repository SQL file execution helpers:
  - `VendorRepository._sql(...)`
  - `VendorRepository._query_file(...)`
  - `VendorRepository._execute_file(...)`
  - cached file loading via `_read_sql_file(...)`.
- Refactored ingestion/insert/update/reporting paths in `VendorRepository` to execute SQL from external `.sql` files instead of embedding mutation/report SQL inline.
- Migrated core mutation flows to file-backed SQL:
  - vendor/offering create + update
  - offering owner/contact add/remove
  - contract/demo mapping
  - project create/update and related mapping rows
  - project demo create/update/remove
  - project notes, document link create/update/remove
  - change request + workflow event writes
  - vendor profile apply flow (including history close/insert)
  - contract cancellation record flow
  - role/scope grants + access audit
  - user settings + usage logging writes.
- Migrated reporting/read aggregation SQL for dashboard and executive/report datasets to file-backed SQL (vendor inventory/project portfolio/supporting owner coverage data pulls, spend/renewal/risk rollups, demo outcomes, contract cancellations, grants lists).

## 2026-02-09T21:26:44Z | VC-20260209-212644-6321
- Implemented Step C typeahead API surface for large reference selection workloads:
  - `GET /api/vendors/search`
  - `GET /api/offerings/search`
  - `GET /api/projects/search`
- Reworked project create/edit forms to remove preloaded vendor/offering dropdowns and use on-demand typeahead selection (server-rendered Jinja + lightweight vanilla JS).
- Reworked Project Offerings quick-attach controls to typeahead vendor/offering search with no full preload, while preserving auto-attach vendor behavior.
- Updated project vendor filtering UI on `/projects` to use vendor typeahead instead of loading full vendor option lists.
- Added backend helpers for selected entity hydration (`get_vendors_by_ids`, `get_offerings_by_ids`) and server-side dedupe/auto-attach behavior when offerings imply vendor linkage.
- Added tests for new typeahead APIs covering vendor, offering, and project search paths in mock mode.

## 2026-02-09T21:13:44Z | VC-20260209-211344-6816
- Completed Step A stability fix: updated all router template rendering calls to the modern Starlette signature `TemplateResponse(request, template, context, ...)`, removing deprecation warnings.
- Added server-side Vendor 360 list paging/sort/search controls with URL state:
  - `q`, `page`, `page_size`, `sort_by`, `sort_dir`
  - retained backward-compatible `search` query support.
- Added repository-level paged vendor query method for mock/local/dbx modes:
  - `list_vendors_page(...)` with validated sort columns and deterministic ordering.
- Added batched offering lookup for current vendor page to avoid per-row offering queries:
  - `list_vendor_offerings_for_vendors(...)`.
- Persisted vendor list preferences in user settings (`vendor360_list.list_prefs`) for:
  - search text, filters, page size, and sort state.
- Updated Vendor 360 UI:
  - page size selector
  - sortable headers
  - previous/next pager with row range summary
  - stable settings toggle URL preserving list state.
- Updated Vendor field-matrix save behavior to merge with existing vendor list preferences instead of overwriting them.
- Added tests for Vendor 360 server-side pagination/sort behavior and preference persistence with `q` search.

## 2026-02-09T20:53:54Z | VC-20260209-205354-3900
- Added a new root `README.md` with complete project overview, run modes, schema references, and validation commands.
- Expanded `app/README.md` to reflect current modules (including Projects and Reports), runtime modes, and operational startup paths.
- Added a dedicated database documentation section:
  - `docs/database/README.md`
  - `docs/database/schema-reference.md`
- Added local SQL schema inventory query: `app/local_db/sql/queries/040_schema_inventory.sql`.
- Updated local query docs (`app/local_db/sql/queries/README.md`) and local DB runtime notes (`app/local_db/README.md`).
- Updated architecture model docs to include project/document app tables and reports module:
  - `docs/architecture/04-data-model-unity-catalog.md`
  - `docs/architecture/07-application-architecture.md`
- Added SQL bootstrap guide `docs/architecture/sql/README.md`.
- Updated Databricks bootstrap DDL (`docs/architecture/sql/02_core_tables.sql`) with:
  - `core_contract.annual_value`
  - full project/document workflow tables (`app_project*`, `app_document_link`)

## 2026-02-09T20:35:27Z | VC-20260209-203527-2688
- Added a new permission-gated Reports workspace at `/reports` for report-capable users.
- Added custom report builder flows with filters and row limits for:
  - Vendor Inventory
  - Project Portfolio
  - Contract Renewals
  - Demo Outcomes
  - Owner Coverage (owner-to-entity workload view)
- Added on-screen result preview with selectable columns via a column matrix.
- Added CSV extract download endpoint: `GET /reports/download`.
- Added email extract request endpoint: `POST /reports/email` (queues request metadata in usage logs for downstream processing).
- Added report telemetry events: `report_run`, `report_download`, and `report_email_request`.
- Added role capability `can_report` and updated top navigation to show a Reports tab for authorized users.
- Added pytest coverage for reports access control, report execution, CSV download, and email request flow.

## 2026-02-09T20:20:13Z | VC-20260209-202013-7134
- Added standalone project document-link write route: `POST /projects/{project_id}/docs/link`.
- Updated Project `Documents` tab so `+ Add Link` works without a linked vendor (supports project-first workflow).
- Kept URL-based smart defaults on project docs (`doc_type` inference + default title generation) with `https://` validation.
- Added regression coverage to confirm vendor-less projects appear on `/projects` and can receive document links before vendor assignment.

## 2026-02-09T20:09:48Z | VC-20260209-200948-6283
- Reworked Project Offerings tab controls into a two-dropdown inline layout (Vendor + Offering) with attach action inline.
- Added auto-attach vendor behavior: selecting a non-linked vendor in the vendor dropdown now triggers project vendor attachment automatically.
- Kept offering dropdown filtered by selected vendor and reset hidden/invalid selections when the vendor filter changes.
- Moved `Add Vendor` and `Add Offering` actions below their respective dropdowns per requested layout.
- Updated Add Offering create link behavior to require selected vendor and route through `/projects/{project_id}/offerings/new`.

## 2026-02-09T20:00:55Z | VC-20260209-200055-7359
- Updated project create/edit forms so offering choices are filtered by selected vendor(s) using client-side filtering.
- Updated Project Offerings tab actions:
  - `Add Vendor` now opens vendor creation form (`/vendors/new`) with return to project offerings.
  - `Add Offering` now opens offering creation flow for the selected vendor via new redirect route.
- Added route `GET /projects/{project_id}/offerings/new` to safely redirect to vendor-scoped offering creation.
- Kept explicit attach-existing workflows via `Attach Vendor` and `Attach Offering` actions on Project Offerings tab.
- Added disabled-state handling for offering-create button until a vendor is selected.

## 2026-02-09T19:50:22Z | VC-20260209-195022-1846
- Renamed project `Changes` section to `Notes` in project navigation and routing, with compatibility redirect from `/projects/{project_id}/changes` to `/projects/{project_id}/notes`.
- Moved project quick actions so they render only on the `Summary` tab.
- Added ownership editing on the `Ownership` tab for authorized users via `POST /projects/{project_id}/owner/update`.
- Added project `Offerings` tab quick-add actions for authorized users:
  - `POST /projects/{project_id}/vendors/add`
  - `POST /projects/{project_id}/offerings/add`
- Enhanced project tab data rendering to support multi-vendor projects more consistently (vendor-aware demo links/actions and aggregated offering/owner/contact context).
- Updated project section templates to display vendor context in offerings/demos and expose permission-gated controls on Ownership/Demos/Documents/Notes tabs.
- Added/updated tests for project notes route behavior and quick-add vendor/offering flows.

## 2026-02-09T19:37:09Z | VC-20260209-193709-6921
- Added vendor-optional project creation flow at `/projects/new` so users can create projects before selecting vendors.
- Added global project edit flow at `/projects/{project_id}/edit` with support for attaching one or many vendors and linked offerings.
- Added project-to-vendor mapping support in repository logic and runtime schema (`app_project_vendor_map`) while preserving backward compatibility with legacy `app_project.vendor_id`.
- Updated project list/filter logic to include projects through vendor mappings (not just primary vendor ID).
- Updated project templates and navigation to support standalone project edit/create actions and multi-vendor visibility on project summary.
- Updated local SQLite schema/seed to include `app_project_vendor_map` and allow nullable primary `vendor_id` on `app_project`.
- Added tests for vendor-optional project creation and later multi-vendor attachment workflow.

## 2026-02-09T19:23:03Z | VC-20260209-192303-4168
- Improved New Vendor validation UX to preserve entered values and show inline field-level errors instead of clearing the form on failure.
- Added server-side validation and clear error messaging for required `Owner Org ID` before persistence attempts.
- Reworked `Owner Org ID` input into a dropdown of existing orgs with a `+ Add new org` option and conditional input for new org IDs.
- Added explanatory helper text clarifying `Owner Org ID` as the internal owning organization.
- Added styling for invalid-field highlighting and hidden-field toggling.
- Added mock-mode test coverage to confirm validation errors keep form values and mark invalid fields.

## 2026-02-09T19:17:02Z | VC-20260209-191702-5834
- Added local runtime mode flags to config: `TVENDOR_USE_LOCAL_DB` and `TVENDOR_LOCAL_DB_PATH`.
- Updated DB client to support SQLite execution in local mode, including `%s` to `?` parameter conversion and schema-prefix normalization.
- Updated repository table resolution and runtime setup logic so local DB mode uses local table names and skips Databricks runtime DDL bootstrap.
- Updated repository current-user resolution for local DB mode to use `TVENDOR_TEST_USER` fallback.
- Updated `launch_app.bat` defaults to run against the local DB (`TVENDOR_USE_MOCK=false`, `TVENDOR_USE_LOCAL_DB=true`) and auto-initialize DB if missing.
- Added local DB runtime env guidance to `app/local_db/README.md`.

## 2026-02-09T19:12:05Z | VC-20260209-191205-7412
- Refactored local DB bootstrap to file-based SQL folders under `app/local_db/sql` with `schema/`, `seed/`, and `queries/`.
- Updated `app/local_db/init_local_db.py` to execute ordered SQL scripts from folders (or optional explicit schema/seed files), with default seeded initialization and `--skip-seed` support.
- Added `app/local_db/sql/seed/001_seed_mock_data.sql` to seed a complete mock-aligned dataset across vendor, offering, contracts, demos, projects, docs, security, and audit workflow tables.
- Added reusable query files in `app/local_db/sql/queries/` including broad Vendor 360 search and projects-by-owner lookups to keep SQL out of Python.
- Converted `app/local_db/schema_sqlite.sql` into a compatibility stub and documented canonical SQL locations.
- Updated local DB docs and bootstrap batch messaging to reflect schema + seed initialization.

## 2026-02-09T19:04:51Z | VC-20260209-190451-3025
- Added a full local SQLite schema bootstrap for the complete `twvendor` logical model (source, core, history, audit, app, security, and reporting views).
- Added `app/local_db/schema_sqlite.sql` with complete local DDL and indexes for key access paths.
- Added `app/local_db/init_local_db.py` to initialize/reset the local DB and report created table/view counts.
- Added `init_local_db.bat` for one-command local database creation from repo root.
- Added local DB usage documentation in `app/local_db/README.md`.
- Updated `.gitignore` to exclude generated local SQLite database files (`app/local_db/*.db`).

## 2026-02-09T19:00:42Z | VC-20260209-190042-8569
- Added explicit add-object quick actions on standalone project pages for users with edit permissions (`+ Add Demo`, `+ Add Document`, `+ Add Note`).
- Added first-class Project Notes support with repository methods, runtime table bootstrap (`app_project_note`), mock data parity, telemetry (`project_note_add`), and audited writes.
- Added standalone project note creation route: `POST /projects/{project_id}/notes/add` with permission and locked-mode enforcement.
- Enhanced standalone project summary/changes pages to show note counts and note history, including recent notes on summary.
- Added test coverage for adding notes from standalone project pages.

## 2026-02-09T18:53:06Z | VC-20260209-185306-9087
- Added standalone project sectioned views at `/projects/{project_id}/{section}` for `summary`, `ownership`, `offerings`, `demos`, `docs`, and `changes`.
- Implemented project-specific section navigation so project pages no longer jump into Vendor 360 section tabs.
- Updated project list/open flows to point to standalone project routes and kept vendor-scoped project routes as compatibility redirects.
- Updated project write redirects (create/edit/demo actions and docs linking) to return users to standalone project sections.
- Added explicit vendor-demo backlinking in Project Demos section to keep traceability to vendor-level demo history.
- Added/updated tests for standalone project route behavior and project section rendering paths.

## 2026-02-09T18:45:20Z | VC-20260209-184520-5918
- Reworked top navigation to primary sections only: Dashboard, Vendor 360, Projects, and permission-gated Admin.
- Added a dedicated global Projects view at `/projects` with filters (search/status/vendor), cross-vendor project list, and quick open/edit actions.
- Added a fast create flow from Projects page (`/projects/new?vendor_id=...`) that routes users into vendor-scoped project creation.
- Updated vendor project pages to highlight the Projects navigation context for easier workflow continuity.
- Added test coverage for Projects home and new-project redirect flow.

## 2026-02-09T18:37:59Z | VC-20260209-183759-9117
- Added first-class Projects workflow for Vendor 360: projects list, project detail, create/edit forms, linked-offering mapping, and project activity view.
- Added Project Demo management: create/map/update/remove flows plus demo-level document linking from project detail pages.
- Added Document Links hub behavior (links only, no uploads) for vendor, project, offering, and project-demo entities with telemetry and audited write paths.
- Added URL smart defaults for document links: server and UI doc-type suggestion, generated default titles, `https://` validation, and doc-type enum validation.
- Expanded repository/runtime support with new app tables (`app_project`, `app_project_offering_map`, `app_project_demo`, `app_document_link`) and full mock-mode parity.
- Updated Vendor 360 summary with Projects/Documents preview cards and added offerings-page document link controls.
- Added test coverage for doc-link heuristics and project/demo/doc end-to-end flows in mock mode.

## 2026-02-09T18:16:37Z | VC-20260209-181637-9314
- Expanded Vendor 360 search to match related entity data (offerings, contracts, vendor/offering owners, contacts, demos, and key vendor/source fields).
- Added resilient SQL search with fallback behavior if related-table lookups are unavailable.
- Updated Vendor 360 search UI copy and placeholder to reflect broad cross-entity search behavior.
- Added test coverage for related-data search (contract ID and business owner principal).

## 2026-02-09T17:54:57Z | VC-20260209-175457-4821
- Reworked Vendor 360 summary into a high-level overview with KPIs, key facts, primary contacts, top offerings preview, and collapsible spend/raw-field sections.
- Added dedicated offerings deep-dive route and page at `/vendors/{vendor_id}/offerings` with offering-level metrics and unassigned contract/demo mapping controls.
- Added vendor creation flow (`GET/POST /vendors/new`) and offering creation flow (`GET/POST /vendors/{vendor_id}/offerings/new`).
- Upgraded offering detail page to support editing offering fields, moving contract/demo mappings, and basic add/remove actions for offering owners and contacts.
- Added repository write APIs for vendor/offering creation, offering updates, mapping actions, and owner/contact CRUD with mock-mode parity and best-effort auditing.
- Enforced `locked_mode` and role checks across all vendor/offering write actions.
- Added telemetry events for vendor/offering create and offering-level write actions.
- Added pytest coverage for Vendor 360 baseline load, permission behavior for vendor create form, vendor creation, offering creation, and mapping flows in mock mode.
