@echo off
setlocal
set "VC_DEV_IDENTITY_ENABLED=true"
set "VC_DEV_USER=editor@example.com"
set "VC_DEV_EMAIL=editor@example.com"
set "VC_DEV_NAME=Vendor Editor"
set "VC_DEV_GROUPS=vendor_editor"
call "%~dp0launch_app.bat" --no-persona-prompt %*
endlocal
