@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  exit /b 2
)
if not exist ".env" (
  echo Missing .env. Run setup.bat first.
  exit /b 2
)
call ".venv\Scripts\activate.bat"
set /a BACKOFF=5
:start
if exist "data\KILL" (
  echo data\KILL is present. Deliberate stop; no restart. Review positions before removing it.
  exit /b 0
)
python -m app.main %*
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" exit /b 0
if "%RESULT%"=="2" exit /b 2
if "%RESULT%"=="130" exit /b 0
if "%RESULT%"=="-1073741510" exit /b 0
rem A smoke failure must be returned once, not restarted indefinitely.
for %%A in (%*) do if "%%~A"=="--smoke-seconds" exit /b %RESULT%
if exist "data\KILL" exit /b 0
echo Unexpected exit %RESULT%. Retrying in %BACKOFF% seconds. Ctrl+C or data\KILL stops restart.
powershell.exe -NoProfile -NonInteractive -Command "Start-Sleep -Seconds %BACKOFF%"
if errorlevel 1 exit /b 1
set /a BACKOFF=BACKOFF*2
if %BACKOFF% GTR 300 set /a BACKOFF=300
goto start
