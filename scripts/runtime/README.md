# Runtime Scripts

## Prerequisite
```powershell
pip install -r requirements-rebuild.txt
```

## Clean Runtime Schema
```powershell
./scripts/runtime/run_clean_rebuild.ps1
```

## Quality Gates
```powershell
./scripts/runtime/run_quality_checks.ps1
```

## Browser E2E
```powershell
./scripts/runtime/run_e2e_vendor_flow.ps1
```

## Performance Baseline
```powershell
./scripts/runtime/run_perf_baseline.ps1
```

## Cutover Scripts
```powershell
./scripts/runtime/cutover_preflight.ps1 -Environment local
./scripts/runtime/cutover_execute.ps1 -Environment local -BaseUrl http://localhost:8010
./scripts/runtime/cutover_smoke.ps1 -BaseUrl http://localhost:8010
./scripts/runtime/rollback_prepare.ps1 -Environment local
```
