# V1 Schema Build Package

This folder contains the V1 data-layer schema rebuild scripts.

## Layout
- `local_db/` SQLite-compatible schema scripts for local development/testing.
- `databricks/` Databricks SQL schema scripts for Unity Catalog environments.

## Execution Order
1. `00_create_v1_schema.sql`
2. `01_create_lookup_tables.sql`
3. `02_create_core_tables.sql`
4. `03_create_assignment_tables.sql`
5. `04_create_governance_tables.sql`
6. `05_create_functional_parity_bridge.sql`
7. `06_create_functional_runtime_compat.sql`
8. `07_create_reporting_views.sql`
9. `90_create_indexes.sql`

## Functional Parity Requirement
- POC data migration is not part of V1 deployment.
- No legacy data conversion is performed.
- Functional parity is mandatory: V1 must preserve all current application capabilities.
- Use the execution plan in `docs/architecture/14-v1-functional-parity-execution-plan.md` as the gate for runtime cutover.

## V1 Build Approach
1. Build normalized V1 canonical entities (already in progress).
2. Add compatibility bridge objects for any runtime-required functionality not yet migrated.
3. Migrate application repositories/routes module-by-module to canonical V1 entities.
4. Remove compatibility bridge only after parity test matrix is fully green.

## Deployment Policy
- V1 is deployed as a clean rebuild.
- Existing schema/data for the target V1 deployment is dropped and recreated.
- This is destructive by design for new deployment environments.

## Notes
- Use lookup IDs/FKs for governed dimensions.
- Do not write free-form LOB/service type/owner role/contact type values into core tables.
- Keep schema evolution explicit and versioned after V1 baseline is established.

## Orchestrator Script
Use a single runner for both local and Databricks:

`setup/v1_schema/run_v1_schema.py`

## Clean Deployment Wrapper (Recommended)
Use the one-command PowerShell wrapper that always enforces destructive rebuild mode (`--recreate`):

`setup/v1_schema/deploy_v1_clean.ps1`

### Local clean deploy
```powershell
powershell -ExecutionPolicy Bypass -File setup/v1_schema/deploy_v1_clean.ps1 -Target local
```

### Databricks clean deploy (render only)
```powershell
powershell -ExecutionPolicy Bypass -File setup/v1_schema/deploy_v1_clean.ps1 -Target databricks -Catalog vendorcat_dev -Schema vendorcat_v1
```

### Databricks clean deploy (execute)
```powershell
powershell -ExecutionPolicy Bypass -File setup/v1_schema/deploy_v1_clean.ps1 -Target databricks -Catalog vendorcat_dev -Schema vendorcat_v1 -Execute -DatabricksServerHostname <workspace-hostname> -DatabricksHttpPath <sql-http-path> -DatabricksToken <pat-token>
```

### Local execution (SQLite)
```bash
python setup/v1_schema/run_v1_schema.py --target local --execute --recreate
```

Verify schema quality gates (required tables, foreign keys, uniqueness):
```bash
python setup/v1_schema/verify_v1_schema_quality.py --db-path setup/local_db/twvendor_local_v1.db
```

Optional local DB path:
```bash
python setup/v1_schema/run_v1_schema.py --target local --execute --recreate --db-path setup/local_db/twvendor_local_v1.db
```

### Databricks render only (default)
```bash
python setup/v1_schema/run_v1_schema.py --target databricks --catalog vendorcat_dev --schema vendorcat_v1 --recreate
```

### Databricks execute directly
```bash
python setup/v1_schema/run_v1_schema.py \
	--target databricks \
	--catalog vendorcat_dev \
	--schema vendorcat_v1 \
	--recreate \
	--execute \
	--databricks-server-hostname <workspace-hostname> \
	--databricks-http-path <sql-http-path> \
	--databricks-token <pat-token>
```

## Seeding (New)

Use the unified seed runner:

`setup/v1_schema/run_v1_seed.py`

### Local baseline seed
```bash
python setup/v1_schema/run_v1_seed.py --target local --db-path setup/local_db/twvendor_local_v1.db --seed-profile baseline
```

### Local full synthetic seed
```bash
python setup/v1_schema/run_v1_seed.py --target local --db-path setup/local_db/twvendor_local_v1.db --seed-profile full
```

### Databricks seed (render only)
```bash
python setup/v1_schema/run_v1_seed.py --target databricks --catalog vendorcat_dev --schema vendorcat_v1
```

### Databricks seed (execute)
```bash
python setup/v1_schema/run_v1_seed.py \
	--target databricks \
	--catalog vendorcat_dev \
	--schema vendorcat_v1 \
	--execute \
	--databricks-server-hostname <workspace-hostname> \
	--databricks-http-path <sql-http-path> \
	--databricks-token <pat-token>
```

### Seed coverage verification
```bash
python setup/v1_schema/verify_test_seed_coverage.py --db-path setup/local_db/twvendor_local_v1.db --profile baseline
python setup/v1_schema/verify_test_seed_coverage.py --db-path setup/local_db/twvendor_local_v1.db --profile full
```

For the full use-case inventory and coverage matrix, see:
- `docs/operations/v1-test-use-cases-and-seed-coverage.md`
