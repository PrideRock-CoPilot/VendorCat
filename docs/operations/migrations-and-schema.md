# Migrations and Schema Management

This document defines how to manage database schema changes for VendorCatalog.

## Migration Philosophy

- **Tracked**: Every schema change has a migration file with version number
- **Idempotent**: Running migration twice produces same result
- **Rollbackable**: Every migration includes rollback instructions
- **Testable**: Migrations tested on SQLite dev before Databricks prod
- **Versioned**: `app_schema_version` table tracks applied migrations

## Migration File Structure

**Location**: `setup/databricks/migration_NNN_description.sql`

**Naming**: 
- `migration_007_add_contact_preferred_flag.sql`
- `migration_008_add_user_override_columns.sql`

**Template**:

```sql
-- Migration 007: Add is_preferred_contact to core_vendor_contact
-- Author: Tech Lead
-- Date: 2026-02-15
-- Jira: VENDOR-234

-- Description:
-- Adds is_preferred_contact boolean flag to support contact prioritization feature.

-- Backward Compatibility:
-- Yes - new column has DEFAULT FALSE, existing code continues to work.

-- Rollback Instructions:
-- ALTER TABLE twvendor.core_vendor_contact DROP COLUMN is_preferred_contact;
-- DELETE FROM twvendor.app_schema_version WHERE version_number = 7;

-- ======================
-- FORWARD MIGRATION
-- ======================

ALTER TABLE twvendor.core_vendor_contact 
ADD COLUMN is_preferred_contact BOOLEAN DEFAULT FALSE;

-- Update schema version
INSERT INTO twvendor.app_schema_version (
    version_number,
    description,
    applied_by,
    applied_at
) VALUES (
    7,
    'Add is_preferred_contact flag to core_vendor_contact',
    current_user(),
    current_timestamp()
);

-- Verification query (run after migration to verify)
-- SELECT COUNT(*) FROM twvendor.core_vendor_contact WHERE is_preferred_contact IS NULL;
-- Expected: 0
```

## Migration Workflow

### Step 1: Create Migration File

1. Determine next version number: Check `SELECT MAX(version_number) FROM app_schema_version`
2. Create file: `setup/databricks/migration_NNN_description.sql`
3. Write DDL using template above
4. Include rollback instructions in comments
5. Add verification query

### Step 2: Test on SQLite (Local Dev)

```bash
# Start with clean local DB
python setup/local_db/init_local_db.py

# Apply migration to SQLite
sqlite3 setup/local_db/tvendor.db < setup/databricks/migration_007_add_contact_preferred_flag.sql

# Verify migration applied
sqlite3 setup/local_db/tvendor.db "SELECT * FROM app_schema_version ORDER BY applied_at DESC LIMIT 1;"

# Run app and verify feature works
python -m app.main

# Run tests to ensure no breakage
pytest tests/
```

### Step 3: Code Review

- Include migration file in PR
- Reviewer checks:
  - [ ] Version number incremented correctly
  - [ ] Rollback instructions present
  - [ ] Backward compatible (or breaking change documented)
  - [ ] Verification query included
  - [ ] Tested on SQLite

### Step 4: Apply to Databricks Dev

```bash
# Render SQL with environment variables
python setup/databricks/render_sql.py \
    --template setup/databricks/migration_007_add_contact_preferred_flag.sql \
    --env setup/config/tvendor.dev_pat.env \
    --output /tmp/migration_007_rendered.sql

# Review rendered SQL
cat /tmp/migration_007_rendered.sql

# Apply to Databricks (using databricks-sql-cli or SQL editor)
databricks-sql -e "$(cat /tmp/migration_007_rendered.sql)"

# Verify schema version
databricks-sql -e "SELECT * FROM twvendor.app_schema_version ORDER BY applied_at DESC LIMIT 1;"
```

### Step 5: Deploy Code

- Merge PR to `main`
- Deploy app code to production
- App startup verifies expected schema version (future enhancement)

### Step 6: Apply to Databricks Prod

**Critical**: Always apply to dev/staging before prod.

```bash
# Render for prod environment
python setup/databricks/render_sql.py \
    --template setup/databricks/migration_007_add_contact_preferred_flag.sql \
    --env setup/config/tvendor.env \
    --output /tmp/migration_007_prod.sql

# Apply to Databricks prod
databricks-sql -e "$(cat /tmp/migration_007_prod.sql)"

# Verify
databricks-sql -e "SELECT * FROM twvendor.app_schema_version;"

# Run smoke test
curl https://vendorcat.prod.example.com/health
```

## Migration Version Tracking

### app_schema_version Table

```sql
CREATE TABLE twvendor.app_schema_version (
    version_number INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_by TEXT NOT NULL,  -- username who applied migration
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rollback_notes TEXT  -- optional notes on rollback
);
```

**Usage**:
- Insert row at end of each migration
- Query to see current version: `SELECT MAX(version_number) FROM app_schema_version`
- Query to see migration history: `SELECT * FROM app_schema_version ORDER BY applied_at DESC`

### Schema Version Check on App Startup (Future)

Add to `app/main.py`:

```python
@app.on_event("startup")
async def verify_schema_version():
    expected_version = 7  # Update with each migration
    current_version = repo.get_current_schema_version()
    
    if current_version < expected_version:
        logger.error(f"Schema version mismatch: expected {expected_version}, got {current_version}")
        raise RuntimeError("Database schema out of date. Apply migrations.")
    
    logger.info(f"Schema version verified: {current_version}")
```

## Backward Compatibility

### Safe Changes (Backward Compatible)

- Add new table
- Add new column with DEFAULT value
- Add new index
- Add new view
- Rename column (with view aliasing for old name)

### Breaking Changes (Not Backward Compatible)

- Drop table
- Drop column
- Change column type (without casting)
- Add column without DEFAULT (requires all INSERTs to provide value)
- Rename table (without view aliasing)

**For breaking changes**:
1. Deploy multi-step migration:
   - Step 1: Add new column/table, dual-write old + new
   - Step 2: Backfill data
   - Step 3: Switch reads to new column/table
   - Step 4: Drop old column/table (separate migration)
2. Coordinate deploy: Stop app, apply migration, start app

## Rollback Process

### Automated Rollback (Future)

Create `setup/databricks/rollback_migration.py`:

```python
def rollback_migration(version_number: int):
    migration_file = f"setup/databricks/migration_{version_number:03d}_*.sql"
    
    # Extract rollback SQL from migration file comments
    rollback_sql = extract_rollback_sql(migration_file)
    
    # Execute rollback
    execute_sql(rollback_sql)
    
    # Remove version from app_schema_version
    execute_sql(f"DELETE FROM app_schema_version WHERE version_number = {version_number}")
    
    print(f"Rolled back migration {version_number}")
```

### Manual Rollback

1. Read migration file for rollback instructions (in comments)
2. Execute rollback SQL via Databricks SQL editor
3. Delete row from `app_schema_version`: `DELETE FROM app_schema_version WHERE version_number = 7`
4. Verify: `SELECT MAX(version_number) FROM app_schema_version`
5. Redeploy previous app version if code depends on rolled-back schema

## Migration Testing

### Test Migration on SQLite

Every migration must work on SQLite (local dev) before applying to Databricks.

**SQLite vs Databricks Differences**:
- SQLite: `AUTOINCREMENT` for PK, Databricks: `GENERATED ALWAYS AS IDENTITY`
- SQLite: `TEXT`, Databricks: `STRING`
- SQLite: `INTEGER`, Databricks: `BIGINT` or `INT`

**Solution**: Write migrations compatible with both, or use templating.

### Test Rollback

After applying migration, immediately test rollback on dev environment:

```bash
# Apply migration
databricks-sql -e "$(cat migration_007.sql)"

# Test rollback
databricks-sql -e "ALTER TABLE twvendor.core_vendor_contact DROP COLUMN is_preferred_contact;"
databricks-sql -e "DELETE FROM twvendor.app_schema_version WHERE version_number = 7;"

# Verify rollback
databricks-sql -e "DESCRIBE twvendor.core_vendor_contact;"  # Should not show is_preferred_contact

# Re-apply migration for real
databricks-sql -e "$(cat migration_007.sql)"
```

## Databricks-Specific Optimizations

### Table Properties

Use DELTA table format for performance:

```sql
CREATE TABLE twvendor.core_vendor (
    vendor_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    legal_name STRING NOT NULL,
    -- ... other columns
)
USING DELTA
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true'
);
```

### Partitioning

For large tables (>1M rows), consider partitioning:

```sql
CREATE TABLE twvendor.audit_entity_change (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type STRING,
    change_timestamp TIMESTAMP,
    -- ... other columns
)
USING DELTA
PARTITIONED BY (DATE(change_timestamp))  -- Partition by date
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');
```

### Z-Ordering

For tables with common filter columns:

```sql
-- After table created
OPTIMIZE twvendor.core_vendor ZORDER BY (vendor_status, organization_id);
```

Run monthly or after large data loads.

### Vacuum

Clean up old versions to save storage:

```sql
-- Remove files older than 7 days
VACUUM twvendor.core_vendor RETAIN 168 HOURS;  -- 7 days
```

Run weekly via scheduled job.

## Migration Checklist

Use this for every schema change:

- [ ] **Version number**: Incremented from last migration
- [ ] **File created**: `setup/databricks/migration_NNN_description.sql`
- [ ] **Template followed**: Includes header, description, rollback, forward SQL, version insert
- [ ] **Backward compatible**: Or breaking change documented + multi-step plan
- [ ] **Tested on SQLite**: Migration applied and verified locally
- [ ] **Rollback tested**: Rollback SQL executed and verified on dev
- [ ] **Code updated**: Repository/routers updated to use new schema
- [ ] **Tests pass**: All tests pass with new schema
- [ ] **Applied to dev**: Migration applied to Databricks dev workspace
- [ ] **Applied to prod**: Migration applied to Databricks prod workspace after code deploy
- [ ] **Verified**: Schema version checked in prod, smoke test passed

---

Last updated: 2026-02-15
