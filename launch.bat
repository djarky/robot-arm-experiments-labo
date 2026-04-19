@echo off
setlocal enabledelayedexpansion

title Robot Arm Control System - Master Launcher
color 0A

:menu
cls
echo ======================================================
echo          SISTEMA DE CONTROL DE BRAZO ROBOTICO
echo ======================================================
echo.
echo  1. Iniciar Aplicacion Principal (Seguimiento de Gestos)
echo  2. Iniciar Laboratorio de Experimentos (Control Premium)
echo  3. Actualizar Dependencias
echo  4. Salir
echo.
echo ======================================================
set /p choice="Seleccione una opcion [1-4]: "

if "%choice%"=="1" goto launch_main
if "%choice%"=="2" goto launch_lab
if "%choice%"=="3" goto update_deps
if "%choice%"=="4" goto exit
goto menu

:launch_main
echo Iniciando Aplicacion Principal...
call run.bat
goto exit

:launch_lab
echo Iniciando Laboratorio de Experimentos...
cd experiment_lab
call launch_lab.bat
cd ..
goto exit

:update_deps
echo Actualizando todas las dependencias...
set VENV_DIR=venv
if not exist %VENV_DIR% (
    echo Creando entorno virtual...
    python -m venv %VENV_DIR%
)
call %VENV_DIR%\Scripts\activate
python -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install opencv-python mediapipe PySide6 ursina pyserial requests pygame-ce --trusted-host pypi.org --trusted-host files.pythonhosted.org
echo.
echo Actualizacion completada.
pause
goto menu

:exit
echo Gracias por usar el sistema.
exit /b
