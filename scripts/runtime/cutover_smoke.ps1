param(
  [string]$BaseUrl = "http://localhost:8010"
)

$ErrorActionPreference = "Stop"
$runId = [guid]::NewGuid().ToString()
Write-Host "[cutover_smoke] run_id=$runId base_url=$BaseUrl"

$paths = @("/api/v1/health/live", "/api/v1/health/ready", "/dashboard")

foreach ($path in $paths) {
  $url = "$BaseUrl$path"
  try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
  } catch {
    Write-Error "Smoke request failed url=$url run_id=$runId"
    exit 1
  }

  if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
    Write-Error "Unexpected status=$($response.StatusCode) url=$url run_id=$runId"
    exit 1
  }

  $requestId = $response.Headers["X-Request-ID"]
  Write-Host "[cutover_smoke] ok url=$url status=$($response.StatusCode) request_id=$requestId"
}

Write-Host "[cutover_smoke] success run_id=$runId"
