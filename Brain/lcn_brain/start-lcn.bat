@echo off
cd /d %~dp0
..\..\venv\Scripts\python.exe lcn_server.py
if errorlevel 1 (
    echo LCN server failed to start (exit code %errorlevel%).
    pause
)
