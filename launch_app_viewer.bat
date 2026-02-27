@echo off
setlocal
set "VC_DEV_IDENTITY_ENABLED=true"
set "VC_DEV_USER=viewer@example.com"
set "VC_DEV_EMAIL=viewer@example.com"
set "VC_DEV_NAME=Vendor Viewer"
set "VC_DEV_GROUPS=vendor_viewer"
call "%~dp0launch_app.bat" --no-persona-prompt %*
endlocal
