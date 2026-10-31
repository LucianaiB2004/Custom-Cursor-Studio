@echo off
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0..\editor\scripts\use-theme.ps1" -ThemeFolder "%~dp0."
