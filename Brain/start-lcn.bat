@echo off
:: Change directory to the location of the script (project root)
cd /d "%~dp0.."

:: Prefer global python.exe, fall back to venv
set PYLAUNCHER=python.exe
where %PYLAUNCHER% >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    if exist ".\venv\Scripts\python.exe" (
        set PYLAUNCHER=.\venv\Scripts\python.exe
    ) else (
        echo [ERROR] python.exe not found. Install Python or set up venv/.
        pause
        exit /b
    )
)

:: Start LCN server on localhost:3737
echo Starting LCN server on http://localhost:3737 ...
"%PYLAUNCHER%" Brain\lcn_server.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] LCN server exited with code %ERRORLEVEL%
    pause
)
