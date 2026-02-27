$ErrorActionPreference = "Stop"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}
if (-not $env:DJANGO_SETTINGS_MODULE) {
  $env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
}
if (-not $env:VC_RUNTIME_PROFILE) {
  $env:VC_RUNTIME_PROFILE = "local"
}
if (-not $env:VC_LOCAL_DUCKDB_PATH) {
  $env:VC_LOCAL_DUCKDB_PATH = "src/.local/vendorcatalog.duckdb"
}

python scripts/rebuild/perf_baseline.py --iterations 15 --output docs/rebuild/performance_baseline.md
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
