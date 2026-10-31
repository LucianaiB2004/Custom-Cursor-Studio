@echo off
cd /d "%~dp0..\.."
set "PYTHONPATH=%CD%\src"
start "" ".venv\Scripts\pythonw.exe" -m cursor_studio.app "%~dp0theme.json"
