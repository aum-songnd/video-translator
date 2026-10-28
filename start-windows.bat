@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Chua cai dat. Xem README.md.
  pause
  exit /b 1
)
.venv\Scripts\python.exe app.py
if errorlevel 1 pause
