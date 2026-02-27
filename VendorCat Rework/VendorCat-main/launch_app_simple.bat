@echo off
setlocal enabledelayedexpansion

REM Simple launcher without port fallback complexity
cd /d "%~dp0"

if "%TVENDOR_LOG_FILE%"=="" set "TVENDOR_LOG_FILE=%~dp0launch_app.log"
if "%TVENDOR_KEEP_WINDOW%"=="" set "TVENDOR_KEEP_WINDOW=true"

REM Run main script with output redirect
call :main > "%TVENDOR_LOG_FILE%" 2>&1
set "EXIT_CODE=!ERRORLEVEL!"

REM Display log
type "%TVENDOR_LOG_FILE%"
echo.
echo Log saved to: %TVENDOR_LOG_FILE%
if /I "%TVENDOR_KEEP_WINDOW%"=="true" pause
exit /b !EXIT_CODE!

:main
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Load environment
if "%TVENDOR_ENV_FILE%"=="" set "TVENDOR_ENV_FILE=setup\config\tvendor.env"
if exist "!TVENDOR_ENV_FILE!" (
  echo Loading environment from !TVENDOR_ENV_FILE!
  for /f "usebackq tokens=1* delims==" %%A in (`findstr /R /V "^[ ]*# ^[ ]*$" "!TVENDOR_ENV_FILE!"`) do (
    if not defined %%A set "%%A=%%B"
  )
)

REM Set defaults
if "!TVENDOR_ENV!"=="" set "TVENDOR_ENV=dev"
if "!TVENDOR_USE_LOCAL_DB!"=="" set "TVENDOR_USE_LOCAL_DB=true"
if "!TVENDOR_LOCAL_DB_PATH!"=="" set "TVENDOR_LOCAL_DB_PATH=setup\local_db\twvendor_local.db"
if "!TVENDOR_LOCKED_MODE!"=="" set "TVENDOR_LOCKED_MODE=false"
if "!TVENDOR_OPEN_BROWSER!"=="" set "TVENDOR_OPEN_BROWSER=true"
if "!TVENDOR_LOCAL_DB_AUTO_RESET!"=="" set "TVENDOR_LOCAL_DB_AUTO_RESET=true"
if "!TVENDOR_LOCAL_DB_SEED!"=="" set "TVENDOR_LOCAL_DB_SEED=true"
if "!TVENDOR_LOCAL_DB_SEED_PROFILE!"=="" set "TVENDOR_LOCAL_DB_SEED_PROFILE=baseline"
if "!TVENDOR_LOCAL_DB_REBUILD_MODE!"=="" set "TVENDOR_LOCAL_DB_REBUILD_MODE=always"
if "!PORT!"=="" set "PORT=8000"
if "!TVENDOR_PORT_FALLBACK!"=="" set "TVENDOR_PORT_FALLBACK=true"

REM Check if port is available, try up to 20 alternates
set "FOUND_PORT=0"
set "TRY_PORT=!PORT!"
set /a "MAX_PORT=!PORT!+20"

:port_check_loop
if !TRY_PORT! GTR !MAX_PORT! goto :no_port_found

echo Checking port !TRY_PORT%...
powershell -NoProfile -Command "exit [int](Test-NetConnection -ComputerName 127.0.0.1 -Port !TRY_PORT! -InformationLevel Quiet)" >nul 2>&1
if errorlevel 1 (
  set "PORT=!TRY_PORT!"
  set "FOUND_PORT=1"
  goto :port_found
)

set /a "TRY_PORT=!TRY_PORT!+1"
goto :port_check_loop

:no_port_found
echo ERROR: No available port found between !PORT! and !MAX_PORT!
exit /b 1

:port_found
echo Port !PORT! is available.

REM Setup Python
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  echo Creating .venv...
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create .venv
    exit /b 1
  )
  set "PYTHON_EXE=.venv\Scripts\python.exe"
)

REM Install dependencies if needed
echo Checking dependencies...
!PYTHON_EXE! -m pip install -q -r app\requirements.txt
if errorlevel 1 (
  echo ERROR: Failed to install dependencies
  exit /b 1
)

REM Open browser
if /I "!TVENDOR_OPEN_BROWSER!"=="true" (
  start "" "http://localhost:!PORT!/dashboard"
)

REM Start app
echo.
echo Starting Vendor Catalog at http://localhost:!PORT!/dashboard
echo Press Ctrl+C to stop.
echo.
!PYTHON_EXE! -m uvicorn --app-dir app main:app --host 0.0.0.0 --port !PORT!

exit /b !ERRORLEVEL!
