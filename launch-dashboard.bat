@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-dashboard.ps1" -Mode local -Port 8010
