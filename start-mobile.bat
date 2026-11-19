@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-mobile.ps1"
echo.
echo Pulsa cualquier tecla para cerrar esta ventana (el enlace sigue activo)...
pause >nul
