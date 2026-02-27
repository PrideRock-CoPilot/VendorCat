@echo off
setlocal EnableExtensions

if "%TVENDOR_LOG_FILE%"=="" set "TVENDOR_LOG_FILE=%~dp0launch_app.log"
if "%TVENDOR_KEEP_WINDOW%"=="" set "TVENDOR_KEEP_WINDOW=true"

call :main %* > "%TVENDOR_LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

type "%TVENDOR_LOG_FILE%"
echo.
echo Log saved to: %TVENDOR_LOG_FILE%
if /I "%TVENDOR_KEEP_WINDOW%"=="true" pause
exit /b %EXIT_CODE%

:main
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if "%TVENDOR_ENV_FILE%"=="" set "TVENDOR_ENV_FILE=setup\config\tvendor.env"
if exist "%TVENDOR_ENV_FILE%" (
  echo Loading environment from %TVENDOR_ENV_FILE%
  for /f "usebackq tokens=1* delims==" %%A in (`findstr /R /V "^[ ]*# ^[ ]*$" "%TVENDOR_ENV_FILE%"`) do (
    if /I "%TVENDOR_ENV_FORCE%"=="true" (
      set "%%A=%%B"
    ) else (
      if not defined %%A set "%%A=%%B"
    )
  )
)

if "%TVENDOR_ENV%"=="" set "TVENDOR_ENV=dev"
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
if "%TVENDOR_LOCAL_DB_AUTO_RESET%"=="" set "TVENDOR_LOCAL_DB_AUTO_RESET=true"
if "%TVENDOR_LOCAL_DB_SEED%"=="" set "TVENDOR_LOCAL_DB_SEED=true"
if "%TVENDOR_LOCAL_DB_SEED_PROFILE%"=="" set "TVENDOR_LOCAL_DB_SEED_PROFILE=baseline"
if "%TVENDOR_LOCAL_DB_REBUILD_MODE%"=="" set "TVENDOR_LOCAL_DB_REBUILD_MODE=always"
if "%PORT%"=="" set "PORT=8000"
if "%TVENDOR_PORT_FALLBACK%"=="" set "TVENDOR_PORT_FALLBACK=true"

call :is_port_free %PORT%
if errorlevel 1 goto :port_in_use
goto :port_ready

:port_in_use
echo Port %PORT% is busy. Fallback enabled? %TVENDOR_PORT_FALLBACK%
if /I "%TVENDOR_PORT_FALLBACK%"=="true" goto :port_fallback
echo ERROR: Port %PORT% is already in use.
echo Set TVENDOR_PORT_FALLBACK=true to auto-select a free port.
exit /b 1

:port_fallback
echo Port %PORT% is in use. Searching for a free port...
call :find_free_port %PORT% 20
if errorlevel 1 (
  echo ERROR: No available port found near %PORT%.
  exit /b 1
)
echo Selected fallback port %PORT%.
goto :port_ready

:port_ready
echo Port ready: %PORT%

if /I "%TVENDOR_USE_LOCAL_DB%"=="true" (
  call :validate_local_db_env
  if errorlevel 1 exit /b 1
)

if "%TVENDOR_BOOTSTRAP_DEPS%"=="" set "TVENDOR_BOOTSTRAP_DEPS=true"

if not exist ".venv\Scripts\python.exe" (
  if /I "%TVENDOR_BOOTSTRAP_DEPS%"=="true" (
    echo Creating local virtual environment .venv...
    python -m venv .venv
    if errorlevel 1 (
      echo.
      echo Failed to create .venv. Install Python 3.11+ and try again.
      pause
      exit /b 1
    )
  )
)

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

if /I "%TVENDOR_BOOTSTRAP_DEPS%"=="true" (
  echo Ensuring dependencies are installed...
  %PYTHON_EXE% -m pip install -r app\requirements.txt
  if errorlevel 1 (
    echo.
    echo Failed to install dependencies. Run:
    echo   %PYTHON_EXE% -m pip install -r app\requirements.txt
    pause
    exit /b 1
  )
  echo.
)

echo Launching Vendor Catalog app...
echo Using Python: %PYTHON_EXE%
echo TVENDOR_ENV=%TVENDOR_ENV%
echo TVENDOR_USE_LOCAL_DB=%TVENDOR_USE_LOCAL_DB%
echo TVENDOR_LOCAL_DB_PATH=%TVENDOR_LOCAL_DB_PATH%
echo TVENDOR_LOCKED_MODE=%TVENDOR_LOCKED_MODE%
echo TVENDOR_OPEN_BROWSER=%TVENDOR_OPEN_BROWSER%
echo TVENDOR_LOCAL_DB_AUTO_RESET=%TVENDOR_LOCAL_DB_AUTO_RESET%
echo TVENDOR_LOCAL_DB_SEED=%TVENDOR_LOCAL_DB_SEED%
echo TVENDOR_LOCAL_DB_SEED_PROFILE=%TVENDOR_LOCAL_DB_SEED_PROFILE%
echo TVENDOR_LOCAL_DB_REBUILD_MODE=%TVENDOR_LOCAL_DB_REBUILD_MODE%
echo PORT=%PORT%
echo URL=http://localhost:%PORT%/dashboard
echo.

if /I "%TVENDOR_USE_LOCAL_DB%"=="true" (
  if /I not "%TVENDOR_LOCAL_DB_SEED_PROFILE%"=="baseline" if /I not "%TVENDOR_LOCAL_DB_SEED_PROFILE%"=="full" (
    echo WARNING: Unknown TVENDOR_LOCAL_DB_SEED_PROFILE=%TVENDOR_LOCAL_DB_SEED_PROFILE%
    echo Falling back to TVENDOR_LOCAL_DB_SEED_PROFILE=baseline
    set "TVENDOR_LOCAL_DB_SEED_PROFILE=baseline"
  )

  set "LOCAL_DB_APPLY_ARGS=--skip-seed"
  if /I "%TVENDOR_LOCAL_DB_SEED%"=="true" set "LOCAL_DB_APPLY_ARGS=--seed-profile %TVENDOR_LOCAL_DB_SEED_PROFILE%"
  set "LOCAL_DB_RESET_ARGS=--reset !LOCAL_DB_APPLY_ARGS!"

  set "LOCAL_DB_REBUILD_MODE=%TVENDOR_LOCAL_DB_REBUILD_MODE%"
  if /I not "!LOCAL_DB_REBUILD_MODE!"=="always" if /I not "!LOCAL_DB_REBUILD_MODE!"=="prompt" if /I not "!LOCAL_DB_REBUILD_MODE!"=="keep" (
    echo WARNING: Unknown TVENDOR_LOCAL_DB_REBUILD_MODE=!LOCAL_DB_REBUILD_MODE!
    echo Falling back to TVENDOR_LOCAL_DB_REBUILD_MODE=always
    set "LOCAL_DB_REBUILD_MODE=always"
  )

  set "LOCAL_DB_ACTION="
  if /I "!LOCAL_DB_REBUILD_MODE!"=="always" (
    set "LOCAL_DB_ACTION=clean"
  ) else if /I "!LOCAL_DB_REBUILD_MODE!"=="keep" (
    set "LOCAL_DB_ACTION=keep"
  ) else if /I "!LOCAL_DB_REBUILD_MODE!"=="prompt" (
    if not exist "%TVENDOR_LOCAL_DB_PATH%" (
      set "LOCAL_DB_ACTION=clean"
    ) else (
      set "LOCAL_DB_ACTION_CHOICE=C"
      set /p "LOCAL_DB_ACTION_CHOICE=Local DB action [C=clean rebuild, K=keep data + apply schema updates], default C: "
      if /I not "!LOCAL_DB_ACTION_CHOICE!"=="" set "LOCAL_DB_ACTION_CHOICE=!LOCAL_DB_ACTION_CHOICE:~0,1!"
      if /I "!LOCAL_DB_ACTION_CHOICE!"=="K" set "LOCAL_DB_ACTION=keep"
      if /I not "!LOCAL_DB_ACTION!"=="keep" set "LOCAL_DB_ACTION=clean"
    )
  )
  if "!LOCAL_DB_ACTION!"=="" set "LOCAL_DB_ACTION=clean"

  if /I "!LOCAL_DB_ACTION!"=="clean" (
    echo Rebuilding local DB - clean reset...
    %PYTHON_EXE% setup\local_db\init_local_db.py --db-path "%TVENDOR_LOCAL_DB_PATH%" !LOCAL_DB_RESET_ARGS!
    if errorlevel 1 (
      echo.
      echo Failed to rebuild local database.
      pause
      exit /b 1
    )
    echo.
  ) else (
    echo Applying local DB schema updates while keeping existing data...
    %PYTHON_EXE% setup\local_db\init_local_db.py --db-path "%TVENDOR_LOCAL_DB_PATH%" !LOCAL_DB_APPLY_ARGS!
    if errorlevel 1 (
      if /I "%TVENDOR_LOCAL_DB_AUTO_RESET%"=="true" (
        echo Local DB schema update failed. Rebuilding local DB from scratch...
        %PYTHON_EXE% setup\local_db\init_local_db.py --db-path "%TVENDOR_LOCAL_DB_PATH%" !LOCAL_DB_RESET_ARGS!
        if errorlevel 1 (
          echo.
          echo Failed to rebuild local database.
          pause
          exit /b 1
        )
      ) else (
        echo.
        echo Failed to apply local database schema updates.
        echo Set TVENDOR_LOCAL_DB_AUTO_RESET=true to auto-rebuild local DB when schema updates fail.
        pause
        exit /b 1
      )
    )
    echo.
  )
)

if /I "%TVENDOR_OPEN_BROWSER%"=="true" (
  start "" "http://localhost:%PORT%/dashboard"
)

%PYTHON_EXE% -m uvicorn --app-dir app main:app --host 0.0.0.0 --port %PORT%

if errorlevel 1 (
  echo.
  echo App failed to start. Make sure dependencies are installed:
  echo   pip install -r app\requirements.txt
  echo.
  exit /b 1
)

endlocal & exit /b 0

:validate_local_db_env
setlocal EnableExtensions
if /I "%TVENDOR_ENV%"=="dev" (endlocal & exit /b 0)
if /I "%TVENDOR_ENV%"=="development" (endlocal & exit /b 0)
if /I "%TVENDOR_ENV%"=="local" (endlocal & exit /b 0)
echo ERROR: TVENDOR_USE_LOCAL_DB=true is only allowed for TVENDOR_ENV=dev/development/local.
echo Current TVENDOR_ENV=%TVENDOR_ENV%
endlocal & exit /b 1

:is_port_free
setlocal EnableExtensions
set "CHECK_PORT=%~1"
echo Checking port %CHECK_PORT% availability...
set "PORT_BUSY=false"
for /f "tokens=1-5" %%A in ('netstat -ano ^| findstr /R /C:":%CHECK_PORT%[ ]" ^| findstr /I "LISTENING"') do (
  set "PORT_BUSY=true"
)
if /I "%PORT_BUSY%"=="true" (endlocal & exit /b 1)
endlocal & exit /b 0

:find_free_port
setlocal EnableExtensions
set "START_PORT=%~1"
set "MAX_TRIES=%~2"
if "%MAX_TRIES%"=="" set "MAX_TRIES=10"
set "PORT_CANDIDATE=%START_PORT%"
set /a TRY=0

echo Port search start=%START_PORT%, tries=%MAX_TRIES%

:find_free_port_loop
echo Trying port %PORT_CANDIDATE% (attempt %TRY%)
call :is_port_free %PORT_CANDIDATE%
if not errorlevel 1 (
  endlocal & set "PORT=%PORT_CANDIDATE%" & exit /b 0
)

set /a PORT_CANDIDATE=PORT_CANDIDATE+1
set /a TRY=TRY+1
if %TRY% GTR %MAX_TRIES% (
  endlocal & exit /b 1
)
goto :find_free_port_loop
