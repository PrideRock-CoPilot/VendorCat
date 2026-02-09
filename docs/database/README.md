# Database Guide

This folder documents the full Vendor Catalog data model and how to evolve it safely.

## Canonical Schema Sources
- Local full logical schema: `app/local_db/sql/schema/001_schema.sql`
- Databricks bootstrap SQL: `docs/architecture/sql/`

## Scope
- Single schema boundary: `twvendor`
- Logical table families:
  - `src_`: immutable source landing
  - `core_`: canonical current state
  - `hist_`: version history
  - `app_`: workflow and UI write model
  - `sec_`: security and role mappings
  - `audit_`: immutable event trail
  - `rpt_`: reporting views

## Quick Local Validation
Initialize local DB:
```bat
python app\local_db\init_local_db.py --reset
```

Inspect schema inventory:
```sql
-- app/local_db/sql/queries/040_schema_inventory.sql
SELECT type, name
FROM sqlite_master
WHERE type IN ('table', 'view')
  AND name NOT LIKE 'sqlite_%'
ORDER BY type, name;
```

## Design And Governance References
- `docs/database/schema-reference.md`
- `docs/architecture/04-data-model-unity-catalog.md`
- `docs/architecture/05-security-governance.md`
