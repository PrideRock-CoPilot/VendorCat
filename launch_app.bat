@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

if /I "%~1"=="-h" goto :usage
if /I "%~1"=="--help" goto :usage

set "HOST="
set "PORT="
set "CLEAN_DB=false"
set "AUTO_MIGRATE=true"
set "PORT_FALLBACK=true"
set "PERSONA="
set "PERSONA_PROMPT=true"

:parse_args
if "%~1"=="" goto :after_parse
if /I "%~1"=="--clean-db" (
  set "CLEAN_DB=true"
  shift
  goto :parse_args
)
if /I "%~1"=="--skip-migrate" (
  set "AUTO_MIGRATE=false"
  shift
  goto :parse_args
)
if /I "%~1"=="--persona" (
  if "%~2"=="" (
    echo ERROR: --persona requires a value.
    echo.
    goto :usage_error
  )
  set "PERSONA=%~2"
  set "PERSONA_PROMPT=false"
  shift
  shift
  goto :parse_args
)
if /I "%~1"=="--select-user" (
  set "PERSONA_PROMPT=true"
  shift
  goto :parse_args
)
if /I "%~1"=="--no-persona-prompt" (
  set "PERSONA_PROMPT=false"
  shift
  goto :parse_args
)
if "%HOST%"=="" (
  set "HOST=%~1"
  shift
  goto :parse_args
)
if "%PORT%"=="" (
  set "PORT=%~1"
  shift
  goto :parse_args
)

echo Unknown argument: %~1
echo.
goto :usage_error

:after_parse
if "%HOST%"=="" set "HOST=0.0.0.0"
if "%PORT%"=="" set "PORT=8010"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

if "%DJANGO_SETTINGS_MODULE%"=="" set "DJANGO_SETTINGS_MODULE=vendorcatalog_rebuild.settings"
if "%VC_RUNTIME_PROFILE%"=="" set "VC_RUNTIME_PROFILE=local"
if "%VC_LOCAL_DUCKDB_PATH%"=="" set "VC_LOCAL_DUCKDB_PATH=src\.local\vendorcatalog.duckdb"
if "%VC_OPEN_BROWSER%"=="" set "VC_OPEN_BROWSER=true"
if "%VC_PAUSE_ON_ERROR%"=="" set "VC_PAUSE_ON_ERROR=true"
if /I "%VC_AUTO_MIGRATE%"=="false" set "AUTO_MIGRATE=false"
if /I "%VC_PORT_FALLBACK%"=="false" set "PORT_FALLBACK=false"

if "%PYTHONPATH%"=="" (
  set "PYTHONPATH=src"
) else (
  set "PYTHONPATH=src;%PYTHONPATH%"
)

if "%PERSONA%"=="" (
  if /I "%PERSONA_PROMPT%"=="true" (
    call :select_persona
    if errorlevel 1 goto :fail
  )
)

if not "%PERSONA%"=="" (
  call :apply_persona "%PERSONA%"
  if errorlevel 1 goto :fail
)

call :is_port_free %PORT%
if errorlevel 1 (
  if /I "%PORT_FALLBACK%"=="true" (
    echo Port %PORT% is in use. Searching for a free port...
    call :find_free_port %PORT% 20
    if errorlevel 1 (
      echo ERROR: No available port found near %PORT%.
      goto :fail
    )
    echo Selected fallback port !PORT!.
  ) else (
    echo ERROR: Port %PORT% is already in use.
    goto :fail
  )
)

if /I "%CLEAN_DB%"=="true" (
  echo Running clean runtime migration...
  %PYTHON_EXE% -m apps.core.migrations.run_clean_rebuild
  if errorlevel 1 (
    echo.
    echo Failed to run clean rebuild migration.
    goto :fail
  )
)

if /I "%AUTO_MIGRATE%"=="true" (
  echo Applying Django control migrations...
  %PYTHON_EXE% src\manage.py migrate --noinput
  if errorlevel 1 (
    echo.
    echo Failed to apply Django migrations.
    goto :fail
  )
)

set "BROWSER_HOST=%HOST%"
if "%HOST%"=="0.0.0.0" set "BROWSER_HOST=localhost"

echo Starting VendorCatalog app...
echo Using Python: %PYTHON_EXE%
echo DJANGO_SETTINGS_MODULE=%DJANGO_SETTINGS_MODULE%
echo VC_RUNTIME_PROFILE=%VC_RUNTIME_PROFILE%
echo VC_LOCAL_DUCKDB_PATH=%VC_LOCAL_DUCKDB_PATH%
echo VC_AUTO_MIGRATE=%AUTO_MIGRATE%
if /I "%VC_DEV_IDENTITY_ENABLED%"=="true" (
  echo VC_DEV_IDENTITY_ENABLED=true
  echo VC_DEV_USER=%VC_DEV_USER%
  echo VC_DEV_GROUPS=%VC_DEV_GROUPS%
) else (
  echo VC_DEV_IDENTITY_ENABLED=false
)
echo URL=http://%BROWSER_HOST%:%PORT%/dashboard
echo.

if /I "%VC_OPEN_BROWSER%"=="true" (
  start "" "http://%BROWSER_HOST%:%PORT%/dashboard"
)

%PYTHON_EXE% src\manage.py runserver %HOST%:%PORT%
if errorlevel 1 (
  echo.
  echo VendorCatalog app failed to start.
  echo Install dependencies with:
  echo   pip install -r requirements-rebuild.txt
  goto :fail
)

endlocal
exit /b 0

:usage
echo Usage:
echo   launch_app.bat [host] [port] [--clean-db] [--skip-migrate] [--persona ^<name^>] [--select-user] [--no-persona-prompt]
echo.
echo Persona values:
echo   admin ^| reviewer ^| editor ^| viewer ^| watcher ^| anonymous
echo.
echo Examples:
echo   launch_app.bat
  
echo   launch_app.bat 127.0.0.1 8010
  
echo   launch_app.bat 0.0.0.0 8010 --clean-db
  
echo   launch_app.bat 0.0.0.0 8010 --skip-migrate
  
echo   launch_app.bat --persona admin
  
echo   launch_app.bat --select-user
exit /b 0

:usage_error
echo Usage:
echo   launch_app.bat [host] [port] [--clean-db] [--skip-migrate] [--persona ^<name^>] [--select-user] [--no-persona-prompt]
exit /b 1

:select_persona
echo.
echo Select launch persona:
echo   [1] Admin (full access)
echo   [2] Reviewer (workflow/access review)
echo   [3] Editor (domain write)
echo   [4] Viewer (read-only)
echo   [5] Watcher (observability/report read)
echo   [0] Anonymous/default
choice /C 123450 /N /M "Choose 1/2/3/4/5/0: "
if errorlevel 6 (
  set "PERSONA=anonymous"
  exit /b 0
)
if errorlevel 5 (
  set "PERSONA=watcher"
  exit /b 0
)
if errorlevel 4 (
  set "PERSONA=viewer"
  exit /b 0
)
if errorlevel 3 (
  set "PERSONA=editor"
  exit /b 0
)
if errorlevel 2 (
  set "PERSONA=reviewer"
  exit /b 0
)
if errorlevel 1 (
  set "PERSONA=admin"
  exit /b 0
)
exit /b 1

:apply_persona
set "TARGET_PERSONA=%~1"

if /I "%TARGET_PERSONA%"=="anonymous" (
  set "VC_DEV_IDENTITY_ENABLED=false"
  set "VC_DEV_USER="
  set "VC_DEV_NAME="
  set "VC_DEV_GROUPS="
  set "VC_DEV_EMAIL="
  exit /b 0
)

if /I "%TARGET_PERSONA%"=="admin" (
  set "VC_DEV_IDENTITY_ENABLED=true"
  set "VC_DEV_USER=admin@example.com"
  set "VC_DEV_EMAIL=admin@example.com"
  set "VC_DEV_NAME=Admin User"
  set "VC_DEV_GROUPS=vendor_admin,workflow_reviewer,ops_observer"
  exit /b 0
)

if /I "%TARGET_PERSONA%"=="reviewer" (
  set "VC_DEV_IDENTITY_ENABLED=true"
  set "VC_DEV_USER=reviewer@example.com"
  set "VC_DEV_EMAIL=reviewer@example.com"
  set "VC_DEV_NAME=Workflow Reviewer"
  set "VC_DEV_GROUPS=workflow_reviewer"
  exit /b 0
)

if /I "%TARGET_PERSONA%"=="editor" (
  set "VC_DEV_IDENTITY_ENABLED=true"
  set "VC_DEV_USER=editor@example.com"
  set "VC_DEV_EMAIL=editor@example.com"
  set "VC_DEV_NAME=Vendor Editor"
  set "VC_DEV_GROUPS=vendor_editor"
  exit /b 0
)

if /I "%TARGET_PERSONA%"=="viewer" (
  set "VC_DEV_IDENTITY_ENABLED=true"
  set "VC_DEV_USER=viewer@example.com"
  set "VC_DEV_EMAIL=viewer@example.com"
  set "VC_DEV_NAME=Vendor Viewer"
  set "VC_DEV_GROUPS=vendor_viewer"
  exit /b 0
)

if /I "%TARGET_PERSONA%"=="watcher" (
  set "VC_DEV_IDENTITY_ENABLED=true"
  set "VC_DEV_USER=watcher@example.com"
  set "VC_DEV_EMAIL=watcher@example.com"
  set "VC_DEV_NAME=Ops Watcher"
  set "VC_DEV_GROUPS=ops_observer"
  exit /b 0
)

echo ERROR: Unknown persona "%TARGET_PERSONA%".
echo Use one of: admin, reviewer, editor, viewer, watcher, anonymous.
exit /b 1

:is_port_free
setlocal
set "CHECK_PORT=%~1"
for /f "tokens=1" %%A in ('netstat -ano ^| findstr /R /C:":%CHECK_PORT% .*LISTENING"') do (
  endlocal & exit /b 1
)
endlocal & exit /b 0

:find_free_port
setlocal EnableDelayedExpansion
set "START_PORT=%~1"
set "MAX_TRIES=%~2"
if "!MAX_TRIES!"=="" set "MAX_TRIES=10"
set /a "PORT_CANDIDATE=!START_PORT!"
for /l %%i in (0,1,!MAX_TRIES!) do (
  call :is_port_free !PORT_CANDIDATE!
  if !errorlevel! == 0 (
    for /f %%P in ("!PORT_CANDIDATE!") do (
      endlocal
      set "PORT=%%P"
      exit /b 0
    )
  )
  set /a PORT_CANDIDATE+=1
)
endlocal & exit /b 1

:fail
if /I "%VC_PAUSE_ON_ERROR%"=="true" (
  echo.
  pause
)
exit /b 1
