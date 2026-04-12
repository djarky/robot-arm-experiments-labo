@echo off
REM Launcher para el Laboratorio de Experimentos en Windows
cd /d "%~dp0"
set PYTHONPATH=%PYTHONPATH%;%cd%\..
..\venv\Scripts\python.exe lab_main.py
pause
