@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  py -3 "tools\add.py"
) else (
  python "tools\add.py"
)

echo.
pause
