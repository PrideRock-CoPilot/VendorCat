# Databricks Bootstrap

Bootstrap SQL files in this folder are templates and include `{catalog}` / `{fq_schema}` tokens.
Render them with environment-specific values before running.

## Render For A Target Schema

Example for `a1_dlk.twanalytics`:

```bash
python setup/databricks/render_sql.py --fq-schema a1_dlk.twanalytics
```

Rendered files are written to:

```text
setup/databricks/rendered/
```

## Single Source Config (`app/app.yaml`)

`generate_tvendor_env.py` treats `app/app.yaml` as the primary source of deploy settings.
Only update these per environment:

1. `TVENDOR_CATALOG`
2. `TVENDOR_SCHEMA`

Optional override:

1. `DATABRICKS_WAREHOUSE_ID` (or `DATABRICKS_HTTP_PATH`) if your runtime does not auto-populate SQL path.
2. In Databricks Apps, prefer `valueFrom: "sql-warehouse"` for `DATABRICKS_WAREHOUSE_ID` in `app/app.yaml`.

Then generate runtime env:

```bash
python setup/databricks/generate_tvendor_env.py
```

This writes:

1. `setup/config/tvendor.env`
2. `app/app.yaml` (normalized template unless `--skip-app-yaml-write` is used)

Notes:

1. `DATABRICKS_TOKEN` is left blank intentionally (OAuth-only).
2. `DATABRICKS_SERVER_HOSTNAME` is auto-detected in Databricks when possible; otherwise pass `--workspace-hostname`.
3. You can still override any value with CLI args (for example `--fq-schema`, `--warehouse-id`, `--http-path`).
4. If `--warehouse-id` is not set, generator writes `valueFrom: "sql-warehouse"` for app resource binding.

## Validate Schema + Bootstrap Admin User

Run this inside Databricks to validate required runtime objects and grant admin role(s) to the running user:

```bash
python setup/databricks/validate_schema_and_bootstrap_admin.py --fq-schema a1_dlk.twanalytics
```

Optional role overrides:

```bash
python setup/databricks/validate_schema_and_bootstrap_admin.py \
  --fq-schema a1_dlk.twanalytics \
  --roles vendor_admin,system_admin
```

## One-Step Generate + Bootstrap

You can chain both actions:

```bash
python setup/databricks/generate_tvendor_env.py --bootstrap-admin
```

## Execute Order

Run rendered SQL manually (or via an approved deployment pipeline) in this order:

1. `001_create_databricks_schema.sql`
2. For existing schemas also run:
   - `002_add_offering_lob_service_type.sql`
   - `003_add_lookup_scd_columns.sql`
   - `004_add_offering_profile_ticket.sql`
   - `005_add_offering_profile_dataflow_columns.sql`
   - `006_add_offering_data_flow.sql`

The app validates required objects at startup and fails fast if required runtime objects are missing/inaccessible.

## Runtime Troubleshooting

If the app shows `Schema Bootstrap Required`, call:

```text
GET /api/bootstrap-diagnostics
```

Interpretation:

1. `connectivity_probe` failed: check warehouse app resource binding (`valueFrom: "sql-warehouse"`), OAuth/runtime auth, network access, and warehouse `Can use` permission for the app service principal.
2. `connectivity_probe` passed but table/column probe failed: check Unity Catalog privileges and run missing bootstrap/migration SQL for the configured schema.
