param(
  [ValidateSet('local','databricks')]
  [string]$Environment = "local"
)

$ErrorActionPreference = "Stop"
$runId = [guid]::NewGuid().ToString()
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = "docs/rebuild/cutover_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$packagePath = Join-Path $logDir "rollback_package_$timestamp.md"

@"
# Rollback Package

- Run ID: `$runId`
- Environment: `$Environment`
- Created At: `$(Get-Date -Format o)`

## Rollback Inputs
- Previous deployment artifact identifier
- Previous environment configuration snapshot
- Previous schema target reference

## Rollback Steps
1. Restore previous deployment artifact.
2. Restore previous environment configuration.
3. Validate health endpoints and key smoke routes.
4. Record rollback completion metadata.
"@ | Set-Content -Path $packagePath -Encoding ascii

Write-Host "[rollback_prepare] success run_id=$runId package=$packagePath"
