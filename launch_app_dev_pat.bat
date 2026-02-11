@echo off
setlocal

cd /d "%~dp0"
set "TVENDOR_ENV_FILE=setup\config\tvendor.dev_pat.env"
call launch_app.bat

endlocal
