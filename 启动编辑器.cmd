@echo off
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0editor\scripts\start-editor.ps1" %*
