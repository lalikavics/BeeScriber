@echo off
rem Starts the BeeScriber app (development version, uses the tools\venv Python).
cd /d "%~dp0app"
start "" "%~dp0tools\venv\Scripts\pythonw.exe" -m beescriber
