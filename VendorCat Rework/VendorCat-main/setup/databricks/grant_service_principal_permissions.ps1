param(
    [string]$AppName = "vendorcatalog",
    [string]$Profile = "sso",
    [string]$Catalog = "a1_dlk",
    [string]$Schema = "twvendor",
    [string]$WarehouseName = ""
)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Service Principal Permission Setup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1] Getting app service principal..." -ForegroundColor Yellow
$appJson = & databricks apps get $AppName --profile $Profile --output json
$appData = $appJson | ConvertFrom-Json
$spName = $appData.service_principal_name
$spId = $appData.service_principal_id
Write-Host "SUCCESS Service Principal: $spName (ID: $spId)" -ForegroundColor Green
Write-Host ""

Write-Host "[2] Granting catalog access..." -ForegroundColor Yellow
& databricks catalogs grant-permissions $Catalog --principal $spName --permission USE_CATALOG --profile $Profile 2>&1 | Out-Null
Write-Host "SUCCESS Catalog $Catalog - USE_CATALOG" -ForegroundColor Green
Write-Host ""

Write-Host "[3] Granting schema access..." -ForegroundColor Yellow
$schemaName = "{0}.{1}" -f $Catalog,$Schema
& databricks schemas grant-permissions $schemaName --principal $spName --permission USE_SCHEMA --profile $Profile 2>&1 | Out-Null
Write-Host "SUCCESS Schema $schemaName - USE_SCHEMA" -ForegroundColor Green
& databricks schemas grant-permissions $schemaName --principal $spName --permission MODIFY --profile $Profile 2>&1 | Out-Null
Write-Host "SUCCESS Schema $schemaName - MODIFY" -ForegroundColor Green
Write-Host ""

Write-Host "[4] Granting table permissions..." -ForegroundColor Yellow
$tablesList = & databricks tables list $schemaName --profile $Profile --output json 2>&1
if ($tablesList -and (-not $tablesList.Contains("Error"))) {
    $tablesData = $tablesList | ConvertFrom-Json
    $count = 0
    foreach ($table in $tablesData.objects) {
        $tableName = $table.name
        $fullName = "{0}.{1}.{2}" -f $Catalog,$Schema,$tableName
        & databricks tables grant-permissions $fullName --principal $spName --permission SELECT --profile $Profile 2>&1 | Out-Null
        $count++
    }
    Write-Host "SUCCESS Granted SELECT to $count tables" -ForegroundColor Green
}
Write-Host ""

Write-Host "[5] Warehouse access..." -ForegroundColor Yellow
if (-not [string]::IsNullOrWhiteSpace($WarehouseName)) {
    $whList = & databricks warehouses list --profile $Profile --output json 2>&1
    if ($whList -and (-not $whList.Contains("Error"))) {
        $whData = $whList | ConvertFrom-Json
        $whId = $whData.objects | Where-Object { $_.name -eq $WarehouseName } | Select-Object -ExpandProperty id
        if ($whId) {
            & databricks warehouses grant-permissions $whId --principal $spName --permission CAN_USE --profile $Profile 2>&1 | Out-Null
            Write-Host "SUCCESS Warehouse $WarehouseName - CAN_USE" -ForegroundColor Green
        }
    }
} else {
    Write-Host "INFO No warehouse name specified (optional)" -ForegroundColor Cyan
}
Write-Host ""

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Setup Complete" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Service Principal: $spName" -ForegroundColor White
$catalogSchemaText = "{0}.{1}" -f $Catalog,$Schema
Write-Host "Catalog/Schema: $catalogSchemaText" -ForegroundColor White
