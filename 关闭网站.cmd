@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
".windows\venv\Scripts\python.exe" deploy\windows.py stop
if errorlevel 1 pause
