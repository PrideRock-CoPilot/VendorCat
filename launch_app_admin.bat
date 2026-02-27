@echo off
setlocal
set "VC_DEV_IDENTITY_ENABLED=true"
set "VC_DEV_USER=admin@example.com"
set "VC_DEV_EMAIL=admin@example.com"
set "VC_DEV_NAME=Admin User"
set "VC_DEV_GROUPS=vendor_admin,workflow_reviewer,ops_observer"
call "%~dp0launch_app.bat" --no-persona-prompt %*
endlocal
