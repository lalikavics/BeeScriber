@echo off
rem Same as BeeScriber.bat, but with a console window and the browser developer tools (F12) for error hunting.
chcp 65001 >nul
cd /d "%~dp0app"
set BEESCRIBER_DEBUG=1
"%~dp0tools\venv\Scripts\python.exe" -m beescriber
echo.
echo A BeeScriber leallt.
pause
