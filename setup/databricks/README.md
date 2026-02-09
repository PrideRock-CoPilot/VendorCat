# Databricks Bootstrap

Run `001_create_databricks_schema.sql` manually (or via an approved deployment pipeline) before starting the app in Databricks mode.

The app validates required objects at startup and will fail fast if the target schema is missing or inaccessible.
