@echo off
setlocal

cd /d "%~dp0"
set "TVENDOR_ENV_FILE=setup\config\tvendor.dev_pat.env"
set "TVENDOR_ENV=dev"
set "TVENDOR_USE_LOCAL_DB=true"
set "TVENDOR_DEV_ALLOW_ALL_ACCESS=true"
if "%TVENDOR_TEST_USER%"=="" set "TVENDOR_TEST_USER=dev_admin@example.com"
echo Dev launcher forcing local DB + full access mode:
echo   TVENDOR_USE_LOCAL_DB=%TVENDOR_USE_LOCAL_DB%
echo   TVENDOR_DEV_ALLOW_ALL_ACCESS=%TVENDOR_DEV_ALLOW_ALL_ACCESS%
echo   TVENDOR_TEST_USER=%TVENDOR_TEST_USER%
call launch_app.bat

endlocal
