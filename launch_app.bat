@echo off
setlocal

cd /d "%~dp0"

if "%TVENDOR_ENV_FILE%"=="" set "TVENDOR_ENV_FILE=setup\config\tvendor.env"
if exist "%TVENDOR_ENV_FILE%" (
  echo Loading environment from %TVENDOR_ENV_FILE%
  for /f "usebackq tokens=1* delims==" %%A in (`findstr /R /V "^[ ]*# ^[ ]*$" "%TVENDOR_ENV_FILE%"`) do (
    if not defined %%A set "%%A=%%B"
  )
)

if "%TVENDOR_ENV%"=="" set "TVENDOR_ENV=dev"
if "%TVENDOR_USE_MOCK%"=="" set "TVENDOR_USE_MOCK=false"
if "%TVENDOR_USE_LOCAL_DB%"=="" (
  if /I "%TVENDOR_ENV%"=="dev" (
    set "TVENDOR_USE_LOCAL_DB=true"
  ) else if /I "%TVENDOR_ENV%"=="development" (
    set "TVENDOR_USE_LOCAL_DB=true"
  ) else if /I "%TVENDOR_ENV%"=="local" (
    set "TVENDOR_USE_LOCAL_DB=true"
  ) else (
    set "TVENDOR_USE_LOCAL_DB=false"
  )
)
if "%TVENDOR_LOCAL_DB_PATH%"=="" set "TVENDOR_LOCAL_DB_PATH=setup\local_db\twvendor_local.db"
if "%TVENDOR_CATALOG%"=="" set "TVENDOR_CATALOG=vendor_dev"
if "%TVENDOR_SCHEMA%"=="" set "TVENDOR_SCHEMA=twvendor"
if "%TVENDOR_LOCKED_MODE%"=="" set "TVENDOR_LOCKED_MODE=false"
if "%TVENDOR_OPEN_BROWSER%"=="" set "TVENDOR_OPEN_BROWSER=true"
if "%PORT%"=="" set "PORT=8000"

if /I "%TVENDOR_USE_LOCAL_DB%"=="true" (
  if /I not "%TVENDOR_ENV%"=="dev" if /I not "%TVENDOR_ENV%"=="development" if /I not "%TVENDOR_ENV%"=="local" (
    echo ERROR: TVENDOR_USE_LOCAL_DB=true is only allowed for TVENDOR_ENV=dev/development/local.
    echo Current TVENDOR_ENV=%TVENDOR_ENV%
    exit /b 1
  )
)

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo Launching Vendor Catalog app...
echo Using Python: %PYTHON_EXE%
echo TVENDOR_ENV=%TVENDOR_ENV%
echo TVENDOR_USE_MOCK=%TVENDOR_USE_MOCK%
echo TVENDOR_USE_LOCAL_DB=%TVENDOR_USE_LOCAL_DB%
echo TVENDOR_LOCAL_DB_PATH=%TVENDOR_LOCAL_DB_PATH%
echo TVENDOR_LOCKED_MODE=%TVENDOR_LOCKED_MODE%
echo TVENDOR_OPEN_BROWSER=%TVENDOR_OPEN_BROWSER%
echo PORT=%PORT%
echo URL=http://localhost:%PORT%/dashboard
echo.

if /I "%TVENDOR_USE_LOCAL_DB%"=="true" (
  if not exist "%TVENDOR_LOCAL_DB_PATH%" (
    echo Local DB not found. Initializing...
    %PYTHON_EXE% setup\local_db\init_local_db.py --reset
    if errorlevel 1 (
      echo.
      echo Failed to initialize local database.
      pause
      exit /b 1
    )
    echo.
  )
)

if /I "%TVENDOR_OPEN_BROWSER%"=="true" (
  start "" powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='http://localhost:%PORT%/dashboard'; for ($i=0; $i -lt 60; $i++) { try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process $url; exit 0 } catch { }; Start-Sleep -Milliseconds 500 }; Start-Process $url"
)

%PYTHON_EXE% -m uvicorn --app-dir app main:app --host 0.0.0.0 --port %PORT%

if errorlevel 1 (
  echo.
  echo App failed to start. Make sure dependencies are installed:
  echo   pip install -r app\requirements.txt
  echo.
  pause
)

endlocal
