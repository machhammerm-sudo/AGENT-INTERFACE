@echo off
REM Einmalige Einrichtung: wird nur gebraucht, wenn backend\.venv noch nicht existiert

echo Richte das Backend ein ...
cd /d "%~dp0backend"
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt

if not exist ".env" (
    copy .env.example .env
    echo.
    echo WICHTIG: Oeffne jetzt backend\.env und trage deinen echten
    echo Anthropic-API-Schluessel ein, bevor du Nauteron-Starten.bat ausfuehrst.
    echo.
)

echo Richte das Frontend ein ...
cd /d "%~dp0frontend"
npm install

echo.
echo Fertig! Trage falls noch nicht geschehen deinen API-Schluessel in
echo backend\.env ein und starte danach Nauteron-Starten.bat.
pause
