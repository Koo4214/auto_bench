@echo off
setlocal
set "REPO_ROOT=%~dp0"
set "PYTHON=%REPO_ROOT%venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Project venv python was not found: "%PYTHON%" 1>&2
    exit /b 1
)

cd /d "%REPO_ROOT%"
"%PYTHON%" "%REPO_ROOT%src\app\m1_app.py"
