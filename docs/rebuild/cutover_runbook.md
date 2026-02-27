# Rebuild Cutover Runbook (No Migration)

## Preconditions
- Branch: `rebuild/django5-full-parity`
- All rebuild quality gates green
- Baseline data seed package available
- Rollback owner assigned

## Cutover Steps
1. Run preflight checks.
   - `./scripts/runtime/cutover_preflight.ps1 -Environment local`
   - `./scripts/runtime/cutover_preflight.ps1 -Environment databricks`
2. Provision clean target schema.
   - Local: `./scripts/runtime/run_clean_rebuild.ps1`
   - Databricks: apply rendered schema scripts in `src/schema/rendered/databricks/`
3. Seed baseline reference data only.
4. Switch deployment entrypoint to Django rebuild runtime.
5. Run post-switch smoke checks.
   - `./scripts/runtime/cutover_smoke.ps1 -BaseUrl http://<target-host>`
6. Record cutover metadata and rollback package.
   - `./scripts/runtime/rollback_prepare.ps1 -Environment databricks`

## Execution Script
- `./scripts/runtime/cutover_execute.ps1 -Environment local -BaseUrl http://localhost:8010`
- `./scripts/runtime/cutover_execute.ps1 -Environment databricks -BaseUrl http://<target-host>`

## Rollback Trigger Conditions
- Any smoke endpoint failure
- Readiness endpoint degraded status
- Critical mutation endpoint authorization regression

## Rollback Package
- Generated with `rollback_prepare.ps1`
- Stored in `docs/rebuild/cutover_logs/`

