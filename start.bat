@echo off
:: Change directory to the location of the script
cd /d "%~dp0"

:: Prefer global pythonw.exe, fall back to venv
set PYLAUNCHER=pythonw.exe
where %PYLAUNCHER% >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    if exist ".\venv\Scripts\pythonw.exe" (
        set PYLAUNCHER=.\venv\Scripts\pythonw.exe
    ) else (
        echo [ERROR] pythonw.exe not found. Install Python or set up venv/.
        pause
        exit /b
    )
)

:: Start the application in the background (no terminal window)
start "" "%PYLAUNCHER%" "main.py"
exit
