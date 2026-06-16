@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "PYTHON=%REPO_ROOT%\venv\Scripts\python.exe"
set "VERIFIER=%REPO_ROOT%\scripts\verify_window.py"

if not exist "%PYTHON%" (
    echo Project venv python was not found: "%PYTHON%" 1>&2
    exit /b 1
)

pushd "%REPO_ROOT%" >nul
"%PYTHON%" "%VERIFIER%" %*
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
