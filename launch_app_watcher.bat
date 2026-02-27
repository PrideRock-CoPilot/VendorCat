@echo off
setlocal
set "VC_DEV_IDENTITY_ENABLED=true"
set "VC_DEV_USER=watcher@example.com"
set "VC_DEV_EMAIL=watcher@example.com"
set "VC_DEV_NAME=Ops Watcher"
set "VC_DEV_GROUPS=ops_observer"
call "%~dp0launch_app.bat" --no-persona-prompt %*
endlocal
