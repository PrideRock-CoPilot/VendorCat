# SQL Rollout Notes

## File
- `001_imports_v2_merge_center_migration.sql`

## Purpose
- Adds vendor merge lineage columns on `core_vendor`.
- Creates shared import mapping profile table `app_import_mapping_profile`.
- Backfills admin security actions:
  - `manage_import_mapping_profile`
  - `merge_vendor_records`

## Execution
1. Open a Databricks SQL session with privileges to alter/create in target schema.
2. Set `${CATALOG}` and `${SCHEMA}` placeholders for the environment.
3. Run the script once before app deploy.

## Post-Run Verification
- `DESCRIBE TABLE core_vendor;` includes:
  - `merged_into_vendor_id`
  - `merged_at`
  - `merged_by`
  - `merge_reason`
- `DESCRIBE TABLE app_import_mapping_profile;` succeeds.
- `SELECT role_code, action_code, active_flag FROM sec_role_permission WHERE role_code='vendor_admin' AND action_code IN ('manage_import_mapping_profile','merge_vendor_records');` returns active rows.

## Rollback Guidance
- This migration is additive. Roll back app code first if needed.
- Keep new schema objects in place during rollback to avoid destructive operations.
