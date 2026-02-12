param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath,
    [switch]$Watch,
    [switch]$Full
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..\\..")
$sourcePath = Join-Path $repoRoot "app"
$includeFile = Join-Path $scriptRoot ".databricksinclude"
$excludeFile = Join-Path $scriptRoot ".databricksignore"

$argsList = @(
    "sync"
    $sourcePath
    $WorkspacePath
    "--profile"
    "sso_profile"
    "--include-from"
    $includeFile
    "--exclude-from"
    $excludeFile
)

if ($Full) {
    $argsList += "--full"
}

if ($Watch) {
    $argsList += "--watch"
}

& databricks @argsList
