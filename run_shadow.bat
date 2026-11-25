@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  exit /b 2
)
".venv\Scripts\python.exe" -m app.product_shadow --bale %*
exit /b %errorlevel%
