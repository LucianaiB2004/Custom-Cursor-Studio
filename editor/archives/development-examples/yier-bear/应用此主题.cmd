@echo off
cd /d "%~dp0..\.."
set "PYTHONPATH=%CD%\src"
start "" ".venv\Scripts\pythonw.exe" -m cursor_studio.ui.theme_launcher "%~dp0theme.json"
