# Production Push Bundle

This folder contains a production-oriented Databricks setup bundle:

1. `sql/`: ordered SQL scripts for schema objects and base seeds.
2. `production_push_setup.ipynb`: one notebook to orchestrate apply/drop/truncate/rebuild/validate flows.

## SQL Contents

Object scripts:

1. `00_create_v1_schema.sql`
2. `01_create_lookup_tables.sql`
3. `02_create_core_tables.sql`
4. `03_create_assignment_tables.sql`
5. `04_create_governance_tables.sql`
6. `05_create_functional_parity_bridge.sql`
7. `06_create_functional_runtime_compat.sql`
8. `07_create_reporting_views.sql`
9. `90_create_indexes.sql`

Base seed scripts:

1. `94_seed_critical_reference_data.sql` (dropdown/lookups)
2. `95_seed_base_security_roles.sql` (baseline role definitions + role permissions)
3. `96_seed_help_center.sql` (help content)

## Notebook Operations

Run `production_push_setup.ipynb` and choose widget values:

1. `apply`: apply object SQL, optionally base seed SQL, then validate schema objects.
2. `drop_except`: drop all tables/views except names in `exclude_objects`.
3. `truncate_except`: truncate all tables except names in `exclude_objects` (views are ignored).
4. `rebuild`: run write-permission preflight, drop non-excluded objects, then apply object SQL, seed SQL, and validate.
5. `validate`: validate expected tables/views from object SQL files.

## Required Widgets

1. `catalog`
2. `schema`
3. `sql_root`
4. `operation`
5. `exclude_objects` (comma-separated, case-insensitive names)
6. `include_seed`
7. `include_optimize`
8. `dry_run`
9. `confirm_destructive`

## Notes

1. This notebook is designed for Databricks execution where `spark` and `dbutils` are available.
2. `drop_except`, `truncate_except`, and `rebuild` are destructive operations and require `confirm_destructive=true` unless `dry_run=true`.
3. `dry_run=true` prints SQL without executing it.
4. `rebuild` is the recommended production-reset flow because it validates write permissions before dropping objects.
5. When `CREATE CATALOG IF NOT EXISTS` or `CREATE SCHEMA IF NOT EXISTS` is not permitted, the notebook now continues if the catalog/schema already exist and are usable.

## Contract Validation

Validate that production push SQL creates all app-required tables/views and required columns:

```bash
python setup/production_push/validate_production_push_contract.py
```

The script writes a detailed report to:

```text
setup/production_push/production_push_contract_report.md
```
