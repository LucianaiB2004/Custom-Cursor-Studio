@echo off
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0..\editor\scripts\start-editor.ps1" -Module cursor_studio.ui.theme_launcher -Project "%~dp0project\theme.json"
