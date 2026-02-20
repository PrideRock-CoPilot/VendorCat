# Imports V2 + Vendor Merge Center

## Scope
- Any-layout Imports V2 (CSV/TSV/JSON/XML), including nested XML selector support with `xml_record_path`.
- Shared, admin-managed mapping profiles with legacy user-setting migration fallback.
- No-loss import staging payloads (`source_row_raw`, `unmapped_source_fields`, selector/profile metadata).
- Bundle per-file remap and dependency-ordered apply behavior.
- Vendor Merge Center with preview, conflict decisions, full-graph reassignment, merge lineage/audit.
- Merged-vendor visibility controls (hidden by default, include-on-demand).

## Dependency Map
- Web routes:
  - `app/vendor_catalog_app/web/routers/imports/actions.py`
  - `app/vendor_catalog_app/web/routers/imports/parsing.py`
  - `app/vendor_catalog_app/web/routers/imports/matching.py`
  - `app/vendor_catalog_app/web/routers/vendors/merge_center.py`
  - `app/vendor_catalog_app/web/routers/vendors/common.py`
  - `app/vendor_catalog_app/web/routers/vendors/list_pages.py`
- Repository:
  - `app/vendor_catalog_app/backend/repository_mixins/domains/repository_imports.py`
  - `app/vendor_catalog_app/backend/repository_mixins/domains/reporting/vendors.py`
  - `app/vendor_catalog_app/backend/repository_mixins/domains/reporting/search.py`
- Templates:
  - `app/vendor_catalog_app/web/templates/imports.html`
  - `app/vendor_catalog_app/web/templates/vendor_merge_center.html`
  - `app/vendor_catalog_app/web/templates/vendor_section.html`
  - `app/vendor_catalog_app/web/templates/vendors_list.html`
- Security/permissions:
  - `app/vendor_catalog_app/core/security.py`
  - `app/vendor_catalog_app/core/permissions.py`
- Schema/setup:
  - `setup/v1_schema/local_db/06_create_functional_runtime_compat.sql`
  - `setup/v1_schema/databricks/06_create_functional_runtime_compat.sql`
  - `setup/production_push/sql/06_create_functional_runtime_compat.sql`
  - `setup/v1_schema/local_db/90_create_indexes.sql`
  - `setup/v1_schema/databricks/90_create_indexes.sql`
  - `setup/production_push/sql/90_create_indexes.sql`
  - `setup/v1_schema/verify_v1_schema_quality.py`
- Additive migration scripts:
  - `revisions/imports-v2-merge-center/sql/001_imports_v2_merge_center_migration.sql`
  - `app/vendor_catalog_app/sql/updates/imports_v2_merge_center_migration.sql`

## Rollout Steps
1. Deploy additive schema migration:
   - Run `revisions/imports-v2-merge-center/sql/001_imports_v2_merge_center_migration.sql`.
2. Deploy application code for this branch.
3. Verify security actions for admin role:
   - `manage_import_mapping_profile`
   - `merge_vendor_records`
4. Smoke test:
   - imports preview/remap/apply for CSV + XML.
   - bundle import across vendor/invoice/payment files.
   - merge-center preview/execute and canonical redirect checks.
5. Monitor:
   - audit/workflow events for merge actions.
   - staged payload size growth due to no-loss unmapped retention.

## Rollback Notes
- This release is additive schema-first. No table drops are required for rollback.
- To rollback application behavior:
  - deploy prior app revision.
  - keep additive DB objects in place (safe for prior code paths).
- If operationally required, disable access by removing/deactivating role permissions:
  - `manage_import_mapping_profile`
  - `merge_vendor_records`
- Do not drop `app_import_mapping_profile` or merge columns on `core_vendor` as part of hot rollback.
