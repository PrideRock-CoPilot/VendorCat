$ErrorActionPreference = "Stop"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}
if (-not $env:DJANGO_SETTINGS_MODULE) {
  $env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
}

python -m ruff check src tests_rebuild
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m mypy --config-file mypy-rebuild.ini src tests_rebuild
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/rebuild/validate_schema.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/rebuild/validate_sql_coverage.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests_rebuild/guards/test_rbac_contract.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests_rebuild/guards/test_architecture_guards.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests_rebuild --cov=apps --cov=vendorcatalog_rebuild --cov-report=term-missing --cov-fail-under=80 -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
