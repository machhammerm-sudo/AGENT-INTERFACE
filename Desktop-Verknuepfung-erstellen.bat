@echo off
REM Legt eine Desktop-Verknuepfung mit dem Nauteron-Icon an.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Erstelle-Verknuepfung.ps1"

pause
