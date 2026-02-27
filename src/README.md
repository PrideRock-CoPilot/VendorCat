# VendorCatalog Runtime (`src`)

Canonical runtime profile:
- `VC_RUNTIME_PROFILE=local` for local DuckDB
- `VC_RUNTIME_PROFILE=databricks` for Databricks SQL

## Run
```powershell
pip install -r requirements-rebuild.txt
$env:PYTHONPATH = "src"
$env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
python src/manage.py runserver 0.0.0.0:8010
```

Windows launcher:
```bat
launch_app.bat
```

## Health
- `http://localhost:8010/api/v1/health/live`
- `http://localhost:8010/api/v1/health/ready`
- `http://localhost:8010/api/v1/health`

## Runtime Quality
```powershell
./scripts/runtime/run_clean_rebuild.ps1
./scripts/runtime/run_quality_checks.ps1
./scripts/runtime/run_e2e_vendor_flow.ps1
```
