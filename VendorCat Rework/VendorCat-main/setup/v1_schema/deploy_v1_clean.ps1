param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('local', 'databricks')]
    [string]$Target,

    [string]$DbPath = 'setup/local_db/twvendor_local_v1.db',
    [string]$Catalog = 'vendorcat_dev',
    [string]$Schema = 'vendorcat_v1',
    [switch]$Execute,
    [string]$RenderedOutput = 'setup/databricks/rendered/v1_schema_bundle_clean_rebuild.sql',
    [string]$DatabricksServerHostname = '',
    [string]$DatabricksHttpPath = '',
    [string]$DatabricksToken = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$runner = Join-Path $PSScriptRoot 'run_v1_schema.py'

if (-not (Test-Path $runner)) {
    throw "V1 runner not found: $runner"
}

$pythonCandidates = @(
    (Join-Path $repoRoot '.venv\Scripts\python.exe'),
    'python'
)

$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq 'python') {
        try {
            $null = & $candidate --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $python = $candidate
                break
            }
        }
        catch {
        }
    }
    elseif (Test-Path $candidate) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    throw 'Python executable not found. Activate environment or install Python.'
}

$targetDesc = if ($Target -eq 'local') {
    "LOCAL DB at $DbPath"
}
else {
    "DATABRICKS schema $Catalog.$Schema"
}

if (-not $Force) {
    Write-Host "This operation is DESTRUCTIVE and will drop/recreate $targetDesc" -ForegroundColor Yellow
    $confirmation = Read-Host 'Type REBUILD to continue'
    if ($confirmation -ne 'REBUILD') {
        throw 'Aborted. Destructive clean rebuild was not confirmed.'
    }
}

$cliParams = @(
    $runner,
    '--target', $Target,
    '--recreate'
)

if ($Target -eq 'local') {
    $cliParams += @('--execute', '--db-path', $DbPath)
}
else {
    $cliParams += @('--catalog', $Catalog, '--schema', $Schema)
    if ($RenderedOutput) {
        $cliParams += @('--rendered-output', $RenderedOutput)
    }

    if ($Execute) {
        $cliParams += '--execute'
        if ($DatabricksServerHostname) { $cliParams += @('--databricks-server-hostname', $DatabricksServerHostname) }
        if ($DatabricksHttpPath) { $cliParams += @('--databricks-http-path', $DatabricksHttpPath) }
        if ($DatabricksToken) { $cliParams += @('--databricks-token', $DatabricksToken) }
    }
}

Write-Host "Running clean V1 deployment using: $python $($cliParams -join ' ')" -ForegroundColor Cyan
& $python @cliParams
if ($LASTEXITCODE -ne 0) {
    throw "V1 clean deployment failed with exit code $LASTEXITCODE"
}

if ($Target -eq 'local') {
    $resolvedDbPath = if ([System.IO.Path]::IsPathRooted($DbPath)) { $DbPath } else { Join-Path $repoRoot $DbPath }
    $verify = Join-Path $PSScriptRoot 'verify_v1_schema_quality.py'
    if (Test-Path $verify) {
        Write-Host "Running schema quality verification..." -ForegroundColor Cyan
        & $python $verify --db-path $resolvedDbPath
        if ($LASTEXITCODE -ne 0) {
            throw "Schema quality verification failed with exit code $LASTEXITCODE"
        }
    }
}

Write-Host 'V1 clean deployment completed successfully.' -ForegroundColor Green
