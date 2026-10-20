@echo off
setlocal
rem ============================================================
rem  ELIZA v2 - lanzador sin compilar
rem  - Trabaja SIEMPRE desde la carpeta donde esta este .bat
rem    (doble clic, acceso directo o desde otra consola: da igual).
rem  - Usa el Python de .venv\ directamente; NO usa activate.bat,
rem    que guarda la ruta de la carpeta donde se creo el venv
rem    (si la carpeta se renombra o se copia, apunta al lugar viejo).
rem  - Si .venv no existe o esta roto, lo crea e instala dependencias.
rem ============================================================
cd /d "%~dp0"
title ELIZA v2

set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" goto crear_venv
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 goto venv_roto
"%PY%" -c "import prompt_toolkit, psutil, pylogix" >nul 2>&1
if errorlevel 1 goto instalar
goto ejecutar

:venv_roto
echo [!] El entorno .venv no funciona en esta carpeta/equipo. Se va a recrear...
rmdir /s /q ".venv"

:crear_venv
echo [*] Creando entorno virtual local .venv ...
where py >nul 2>&1
if errorlevel 1 goto crear_con_python
py -3 -m venv ".venv"
goto revisar_venv
:crear_con_python
python -m venv ".venv"
:revisar_venv
if not exist "%PY%" goto sin_python

:instalar
echo [*] Instalando dependencias de requirements.txt ...
"%PY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto error_pip

:ejecutar
"%PY%" eliza2.py %*
if errorlevel 1 pause
exit /b

:sin_python
echo [!] No se pudo crear .venv. Instala Python 3 (con la opcion "Add to PATH")
echo     o verifica que el comando "py" o "python" funcione, y vuelve a intentar.
pause
exit /b 1

:error_pip
echo [!] No se pudieron instalar las dependencias. Revisa la conexion a internet
echo     o el proxy, y vuelve a ejecutar este .bat.
pause
exit /b 1
