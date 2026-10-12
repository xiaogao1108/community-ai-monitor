@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".windows\venv\Scripts\python.exe" goto run
python deploy\windows.py setup
if errorlevel 1 goto failed
:run
".windows\venv\Scripts\python.exe" deploy\open_public.py
if errorlevel 1 goto failed
exit /b 0
:failed
pause
exit /b 1
