# Local Query Library

This folder stores reusable SQL for local SQLite analysis.

## Files
- `count_objects.sql`: Helper used by bootstrap script for object counts.
- `010_vendor_overview.sql`: Vendor KPI rollup.
- `020_projects_by_owner.sql`: Project lookup by owner principal.
- `030_vendor_360_search.sql`: Broad vendor search across related entities.
- `040_schema_inventory.sql`: Full table/view inventory for local schema validation.

## Run example

```bat
sqlite3 app/local_db/twvendor_local.db ".read app/local_db/sql/queries/010_vendor_overview.sql"
```
