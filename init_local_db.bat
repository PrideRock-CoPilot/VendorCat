@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

echo Initializing local SQLite database for twvendor schema and seed data...
echo Using Python: %PYTHON_EXE%
echo.

%PYTHON_EXE% app\local_db\init_local_db.py --reset

if errorlevel 1 (
  echo.
  echo Failed to initialize local database.
  echo Check that Python is available and dependencies are installed.
  pause
  exit /b 1
)

echo.
echo Done. Local DB created at app\local_db\twvendor_local.db
endlocal
