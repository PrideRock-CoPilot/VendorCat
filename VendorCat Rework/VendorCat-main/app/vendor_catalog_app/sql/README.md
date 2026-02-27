# SQL Catalog

This directory stores executable SQL used by the application runtime.

This catalog has been rebuilt for the V1 clean-deployment data layer baseline.
Previous SQL catalog revisions are archived under `archive/sql_catalog/`.

Folders:
- `reporting/`: read/report/dashboard SQL
- `ingestion/`: ingestion lookup SQL
- `inserts/`: insert/mutation SQL
- `updates/`: update/delete mutation SQL

Security note:
- Databricks schema bootstrap SQL lives outside app runtime in `setup/databricks/`.
- The application validates required tables at startup and does not auto-create schema objects.

Repository methods load these files via `VendorRepository._sql(...)` and execute them through `_query_file(...)` / `_execute_file(...)`.
