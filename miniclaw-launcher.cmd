@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"

if exist "%ROOT%web\backend\.venv\Scripts\python.exe" (
  "%ROOT%web\backend\.venv\Scripts\python.exe" -m miniclaw.cli.launcher %*
  exit /b %ERRORLEVEL%
)

python -m miniclaw.cli.launcher %*
exit /b %ERRORLEVEL%
