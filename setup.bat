@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\python.exe" goto checkvenv
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 -c "import sys;sys.exit(sys.version_info < (3,11))"
if errorlevel 1 goto wrongpython
py -3 -m venv .venv
if errorlevel 1 goto failed
goto checkvenv
:usepython
python -c "import sys;sys.exit(sys.version_info < (3,11))"
if errorlevel 1 goto wrongpython
python -m venv .venv
if errorlevel 1 goto failed
:checkvenv
".venv\Scripts\python.exe" -c "import sys;sys.exit(sys.version_info < (3,11))"
if errorlevel 1 goto wrongpython
if /i "%~1"=="--check-only" goto offline
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.lock
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-build-isolation --no-deps -e .
if errorlevel 1 goto failed
if not exist ".env" copy /y ".env.example" ".env" >nul
if not exist "logs" mkdir logs
:offline
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m app.doctor
if errorlevel 1 goto failed
echo Setup complete. Default is PAPER. Secrets are optional for PAPER.
echo Run: run_shadow.bat. Bale requires your explicit app.bale_setup --test first.
exit /b 0
:wrongpython
echo Install 64-bit Python 3.11 or later from python.org, then rerun setup.bat.
exit /b 2
:failed
echo Setup failed. Existing .env and data were not overwritten. Check Python and internet access.
exit /b 1
