@echo off
setlocal
set "VC_DEV_IDENTITY_ENABLED=true"
set "VC_DEV_USER=reviewer@example.com"
set "VC_DEV_EMAIL=reviewer@example.com"
set "VC_DEV_NAME=Workflow Reviewer"
set "VC_DEV_GROUPS=workflow_reviewer"
call "%~dp0launch_app.bat" --no-persona-prompt %*
endlocal
