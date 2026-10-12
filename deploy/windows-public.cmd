@echo off
chcp 65001 >nul
cd /d "%~dp0.."
".windows\venv\Scripts\python.exe" deploy\open_public.py
:done
pause
