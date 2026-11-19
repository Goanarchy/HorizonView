@echo off
chcp 65001 >nul
title HorizonView · Acceso online
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-online.ps1"
