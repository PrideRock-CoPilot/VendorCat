# Local Database Bootstrap

This folder provides a simple local SQLite database bootstrap for the full logical `twvendor` schema.

## Files
- `init_local_db.py`: Creates the SQLite DB, applies schema SQL scripts, and seeds sample data.
- `sql/schema/*.sql`: Canonical schema DDL scripts.
- `sql/seed/*.sql`: Seed scripts (mock-aligned sample data).
- `sql/queries/*.sql`: Reusable local query files.
- `schema_sqlite.sql`: Deprecated compatibility stub pointing to the `sql/` folders.

## Quick Start
From repo root:

```bat
init_local_db.bat
```

Or directly:

```bat
python app\local_db\init_local_db.py --reset
```

Skip seed data:

```bat
python app\local_db\init_local_db.py --reset --skip-seed
```

Use a specific SQL root:

```bat
python app\local_db\init_local_db.py --reset --sql-root app\local_db\sql
```

## Output
- Default DB path: `app/local_db/twvendor_local.db`

## Notes
- SQLite does not support Unity Catalog schemas, so table names are created directly (e.g., `core_vendor`, `app_project`).
- This is for local design/prototyping and schema validation.
- The app supports dedicated local DB runtime mode via `TVENDOR_USE_LOCAL_DB=true`.
- SQL is now file-based so DDL/DML/query changes can be made in `app/local_db/sql` without editing Python code.
- Full schema inventory query: `app/local_db/sql/queries/040_schema_inventory.sql`.

## Run App Against Local DB
Set these environment variables (the `launch_app.bat` defaults now do this):

```bat
set TVENDOR_USE_MOCK=false
set TVENDOR_USE_LOCAL_DB=true
set TVENDOR_LOCAL_DB_PATH=app\local_db\twvendor_local.db
```
