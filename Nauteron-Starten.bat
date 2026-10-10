@echo off
REM Startet das Nauteron Cockpit: Backend + Frontend + Browser

cd /d "%~dp0backend"
if not exist ".venv\Scripts\activate.bat" (
    echo Die virtuelle Umgebung wurde noch nicht eingerichtet.
    echo Bitte zuerst einmalig Setup-Nauteron.bat ausfuehren.
    pause
    exit /b 1
)

start "Nauteron Backend" cmd /k "call .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

cd /d "%~dp0frontend"
start "Nauteron Frontend" cmd /k "npm run dev"

echo Warte kurz, bis beide Server bereit sind ...
timeout /t 6 /nobreak >nul

start "" "http://localhost:5173"

echo.
echo Das Nauteron Cockpit startet jetzt in deinem Browser.
echo Lass die beiden schwarzen Fenster (Backend und Frontend) im Hintergrund offen.
echo Zum Beenden: in beiden Fenstern einfach Strg+C druecken und schliessen.
pause
