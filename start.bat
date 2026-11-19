@echo off
chcp 65001 >nul
title HorizonView
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo No se encontro Python. Instala Python 3 desde python.org y vuelve a intentar.
    pause
    exit /b 1
  )
  set "PY=py -3"
)

echo.
echo  HorizonView
echo  ---------------
echo  Iniciando servidor local en http://127.0.0.1:8770
echo  El navegador se abrira automaticamente.
echo  Para detenerlo, cierra esta ventana o pulsa Ctrl+C.
echo.

start "" "http://127.0.0.1:8770"
%PY% src/server.py

echo.
echo El servidor se ha detenido.
pause
