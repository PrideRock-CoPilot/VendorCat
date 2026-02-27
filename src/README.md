# VendorCatalog Rebuild (Django 5 + HTMX)

This directory contains the clean-slate rebuild foundation.

## Runtime Profiles

- `VC_RUNTIME_PROFILE=local`: DuckDB local runtime
- `VC_RUNTIME_PROFILE=databricks`: Databricks SQL runtime (requires host/http-path/token)

## Run Locally

```powershell
pip install -r requirements-rebuild.txt
$env:PYTHONPATH = "src"
$env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
python src/manage.py runserver 0.0.0.0:8010
```

## Windows Launcher

```bat
launch_rebuild.bat
```

Optional:

```bat
launch_rebuild.bat 0.0.0.0 8010 --clean-db
```

Skip Django control migrations (if needed):

```bat
launch_rebuild.bat 0.0.0.0 8010 --skip-migrate
```

If port `8010` is in use, the launcher auto-selects the next free port.
Set `VC_PORT_FALLBACK=false` to disable fallback.

Open:
- `http://localhost:8010/dashboard`
- `http://localhost:8010/api/v1/health/live`
- `http://localhost:8010/api/v1/health/ready`
- `http://localhost:8010/api/v1/runtime`

## Schema + Quality

```powershell
./scripts/rebuild/run_clean_rebuild.ps1
./scripts/rebuild/run_quality_checks.ps1
./scripts/rebuild/run_e2e_vendor_flow.ps1
```
