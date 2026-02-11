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

## Generate `tvendor.env` For Databricks OAuth

Generate an app config file with Databricks connection values (no PAT token) using:

```bash
python setup/databricks/generate_tvendor_env.py --fq-schema a1_dlk.twanalytics --warehouse-id <warehouse-id>
```

Notes:

1. `DATABRICKS_TOKEN` is left blank intentionally.
2. `DATABRICKS_HTTP_PATH` is derived from `--warehouse-id` when `--http-path` is not supplied.
3. `DATABRICKS_SERVER_HOSTNAME` is auto-detected in Databricks when possible; otherwise pass `--workspace-hostname`.
4. Output defaults to `setup/config/tvendor.env` and can be overridden with `--output-file`.

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
python setup/databricks/generate_tvendor_env.py \
  --fq-schema a1_dlk.twanalytics \
  --warehouse-id <warehouse-id> \
  --bootstrap-admin
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
