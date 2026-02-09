# SQL Catalog

This directory stores executable SQL used by the application runtime.

Folders:
- `reporting/`: read/report/dashboard SQL
- `ingestion/`: ingestion lookup SQL
- `inserts/`: insert/mutation SQL
- `updates/`: update/delete mutation SQL
- `bootstrap/`: one-shot Databricks catalog/schema/table/view bootstrap SQL

Security note:
- `bootstrap/` SQL is intended to be run manually or through a controlled deployment pipeline.
- The application validates required tables at startup and does not auto-create schema objects.

Repository methods load these files via `VendorRepository._sql(...)` and execute them through `_query_file(...)` / `_execute_file(...)`.
