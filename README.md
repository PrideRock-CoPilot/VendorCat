# Vendor Catalog

Canonical runtime for Vendor Catalog is the Django track under `src/`.

## Canonical Track
- Runtime code: `src/`
- Test suite: `tests_rebuild/`
- Runtime scripts: `scripts/runtime/`
- CI workflow: `.github/workflows/ci.yml`

## Local Run
1. Install dependencies:
```powershell
pip install -r requirements-rebuild.txt
```
2. Start app:
```powershell
python src/manage.py runserver 0.0.0.0:8010
```
Or use launcher:
```bat
launch_app.bat
```

## Health Endpoints
- `/api/v1/health/live`
- `/api/v1/health/ready`
- `/api/v1/health`

## Canonical Routes
- `vendor-360`
- `projects`
- `imports`
- `offerings`
- `workflows`
- `reports`
- `contracts`
- `demos`
- `help`
- `access`

## Tests
```powershell
pytest --collect-only -q tests_rebuild
pytest -q tests_rebuild
```

## Quality Checks
```powershell
./scripts/runtime/run_quality_checks.ps1
```

## Consolidation Note
- Legacy non-canonical track was removed from mainline.
- Historical state is preserved in backup tag/branch created before removal.
- See `docs/audit/single-track-baseline/` and `docs/audit/single-track-decision.md`.
