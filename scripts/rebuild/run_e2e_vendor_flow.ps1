param(
  [string]$BaseUrl = "http://127.0.0.1:8011",
  [switch]$SkipServerStart
)

$ErrorActionPreference = "Stop"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "src"
}
if (-not $env:DJANGO_SETTINGS_MODULE) {
  $env:DJANGO_SETTINGS_MODULE = "vendorcatalog_rebuild.settings"
}

$python = "python"
if (Test-Path ".venv\Scripts\python.exe") {
  $python = ".venv\Scripts\python.exe"
}

$serverProcess = $null
$serverStartedHere = $false

try {
  if (-not $SkipServerStart) {
    $uri = [System.Uri]$BaseUrl
    $serverHost = $uri.Host
    $port = $uri.Port

    $serverProcess = Start-Process -FilePath $python -ArgumentList @("src/manage.py", "runserver", "$serverHost`:$port") -PassThru
    $serverStartedHere = $true

    $maxAttempts = 40
    $attempt = 0
    $ready = $false

    while (-not $ready -and $attempt -lt $maxAttempts) {
      $attempt++
      Start-Sleep -Milliseconds 750
      try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/dashboard" -TimeoutSec 5
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
          $ready = $true
        }
      }
      catch {
      }
    }

    if (-not $ready) {
      throw "Timed out waiting for server at $BaseUrl"
    }
  }

  $env:E2E_BASE_URL = $BaseUrl
  & $python tests/e2e/vendor_full_create_flow.py
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}
finally {
  if ($serverStartedHere -and $serverProcess -and -not $serverProcess.HasExited) {
    Stop-Process -Id $serverProcess.Id -Force
  }
}
