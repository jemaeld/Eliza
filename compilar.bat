@echo off
setlocal
rem ============================================================
rem  Compila ELIZA_v2.exe (opcional; para el dia a dia basta eliza2.bat)
rem  Resultado: dist\ELIZA_v2.exe
rem ============================================================
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [!] Primero ejecuta eliza2.bat una vez para crear el entorno .venv
    pause
    exit /b 1
)
"%PY%" -m pip install --disable-pip-version-check -q pyinstaller
if errorlevel 1 goto error
"%PY%" -m PyInstaller --noconfirm --clean --onefile --name ELIZA_v2 eliza2.py
if errorlevel 1 goto error
echo.
echo [*] Listo: dist\ELIZA_v2.exe
echo     Copia el .exe a la carpeta donde quieras que vivan los datos
echo     (config_json\, bitacora\, _acd_store\ se crean junto a el).
pause
exit /b

:error
echo [!] La compilacion fallo. Revisa los mensajes de arriba.
pause
exit /b 1
