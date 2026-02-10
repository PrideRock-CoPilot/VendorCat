# Databricks Bootstrap

Run `001_create_databricks_schema.sql` manually (or via an approved deployment pipeline) before starting the app in Databricks mode.
If the schema already exists from an earlier version, also run:
- `002_add_offering_lob_service_type.sql`
- `003_add_lookup_scd_columns.sql`
- `004_add_offering_profile_ticket.sql`
- `005_add_offering_profile_dataflow_columns.sql`
- `006_add_offering_data_flow.sql`

The app validates required objects at startup and will fail fast if the target schema is missing or inaccessible.
