$ErrorActionPreference = "Stop"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}
if (-not $env:DJANGO_SETTINGS_MODULE) {
  $env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
}

python -m ruff check scripts/runtime tests_rebuild/guards
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m mypy --config-file mypy-rebuild.ini scripts/runtime tests_rebuild/guards
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/runtime/validate_schema.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/runtime/validate_sql_coverage.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests_rebuild/guards/test_rbac_contract.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests_rebuild/guards/test_architecture_guards.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests_rebuild --cov=apps --cov=vendorcatalog_rebuild --cov-report=term-missing --cov-fail-under=70 -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

