param(
  [ValidateSet('local','databricks')]
  [string]$Environment = "local",
  [switch]$SkipPreflight,
  [string]$BaseUrl = "http://localhost:8010"
)

$ErrorActionPreference = "Stop"
$runId = [guid]::NewGuid().ToString()
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = "docs/rebuild/cutover_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir "cutover_$timestamp.json"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}
if (-not $env:DJANGO_SETTINGS_MODULE) {
  $env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
}
$env:VC_RUNTIME_PROFILE = $Environment

Write-Host "[cutover_execute] run_id=$runId environment=$Environment"

if (-not $SkipPreflight) {
  ./scripts/rebuild/cutover_preflight.ps1 -Environment $Environment
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($Environment -eq "local") {
  ./scripts/rebuild/run_clean_rebuild.ps1
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

./scripts/rebuild/cutover_smoke.ps1 -BaseUrl $BaseUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$payload = @{
  run_id = $runId
  environment = $Environment
  base_url = $BaseUrl
  executed_at = (Get-Date).ToString("o")
  status = "success"
}
$payload | ConvertTo-Json | Set-Content -Path $logPath -Encoding ascii
Write-Host "[cutover_execute] success run_id=$runId log=$logPath"
