$ErrorActionPreference = "Stop"

$env:VC_RUNTIME_PROFILE = "local"
if (-not $env:VC_LOCAL_DUCKDB_PATH) {
  $env:VC_LOCAL_DUCKDB_PATH = "src/.local/vendorcatalog.duckdb"
}

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}

python -m apps.core.migrations.run_clean_rebuild
Write-Host "Clean rebuild migration applied to $env:VC_LOCAL_DUCKDB_PATH"
