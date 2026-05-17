@echo off
cd /d "%~dp0"

:: Use python.exe (not pythonw) so errors are visible
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

:: Launch with console visible for debugging
echo Starting OpenCode GUI...
"%PYLAUNCHER%" main.py 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] GUI exited with code %ERRORLEVEL%
    pause
)
exit
