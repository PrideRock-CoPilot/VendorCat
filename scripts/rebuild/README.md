# Rebuild Scripts

## Clean Local Rebuild (DuckDB)

```powershell
./scripts/rebuild/run_clean_rebuild.ps1
```

This drops and recreates the local canonical schema database from
`src/schema/rendered/duckdb/*.sql`.

## Rebuild Quality Checks

```powershell
./scripts/rebuild/run_quality_checks.ps1
```

Runs rebuild-only gates:
- `ruff` for `src` and `tests_rebuild`
- `mypy` for `src` and `tests_rebuild`
- schema contract validation
- SQL coverage validation
- rebuild test suite with coverage `>= 80%`

## Vendor Full E2E Flow

```powershell
./scripts/rebuild/run_e2e_vendor_flow.ps1
```

Runs the browser automation flow in `tests/e2e/vendor_full_create_flow.py`.

- Starts Django server on `http://127.0.0.1:8011`
- Creates a vendor, contact, identifier, offering, and contract
- Verifies resulting pages and records
- Stops the server process automatically

Optional flags:

```powershell
./scripts/rebuild/run_e2e_vendor_flow.ps1 -BaseUrl http://127.0.0.1:8012
./scripts/rebuild/run_e2e_vendor_flow.ps1 -SkipServerStart
```

## Performance Baseline

```powershell
./scripts/rebuild/run_perf_baseline.ps1
```

Generates `docs/rebuild/performance_baseline.md` and stores p50/p95 metrics in `vc_perf_baseline`.

## Cutover Scripts

```powershell
./scripts/rebuild/cutover_preflight.ps1 -Environment local
./scripts/rebuild/cutover_execute.ps1 -Environment local -BaseUrl http://localhost:8010
./scripts/rebuild/cutover_smoke.ps1 -BaseUrl http://localhost:8010
./scripts/rebuild/rollback_prepare.ps1 -Environment local
```
