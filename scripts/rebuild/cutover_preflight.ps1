param(
  [ValidateSet('local','databricks')]
  [string]$Environment = "local"
)

$ErrorActionPreference = "Stop"
$runId = [guid]::NewGuid().ToString()
Write-Host "[cutover_preflight] run_id=$runId environment=$Environment"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}
if (-not $env:DJANGO_SETTINGS_MODULE) {
  $env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
}
$env:VC_RUNTIME_PROFILE = $Environment

python scripts/rebuild/validate_schema.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/rebuild/validate_sql_coverage.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

./scripts/rebuild/run_quality_checks.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Environment -eq "databricks") {
  if (-not $env:DATABRICKS_SERVER_HOSTNAME -or -not $env:DATABRICKS_HTTP_PATH -or -not $env:DATABRICKS_TOKEN) {
    Write-Error "Databricks preflight requires DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN"
    exit 1
  }
}

Write-Host "[cutover_preflight] success run_id=$runId"
