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
