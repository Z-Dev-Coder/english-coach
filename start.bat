@echo off
rem ===================================================================
rem  English Coach - one-click launcher
rem
rem  Safe to run any time. It sets up whatever is missing on first run,
rem  skips that work afterwards, and will not start a second copy of a
rem  server that is already running.
rem ===================================================================
setlocal
title English Coach
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

echo.
echo   English Coach
echo   -------------
echo.

rem --- First run: Python environment --------------------------------
if not exist "%PY%" (
    echo   [setup] Creating the Python environment. This happens once...
    python -m venv .venv || goto :nopython
    "%PY%" -m pip install --upgrade pip >nul 2>&1
    "%PY%" -m pip install -r requirements.txt || goto :failed
)

rem --- First run: environment file ----------------------------------
if not exist ".env" (
    echo   [setup] Creating .env from the example...
    copy /y ".env.example" ".env" >nul
)

rem --- First run: frontend packages ---------------------------------
if not exist "frontend\node_modules" (
    echo   [setup] Installing frontend packages. This takes a minute...
    pushd frontend
    call npm install || (popd & goto :failed)
    popd
)

rem --- Always: apply any new database migrations ---------------------
echo   [db] Checking migrations...
"%PY%" "%~dp0backend\manage.py" migrate --noinput >nul || goto :failed

rem --- Start the API, unless port 8000 is already listening ----------
netstat -ano | findstr /r /c:"TCP.*:8000 .*LISTENING" >nul
if errorlevel 1 (
    echo   [api] Starting the backend on port 8000...
    start "English Coach API" /min cmd /c ""%PY%" "%~dp0backend\manage.py" runserver 8000"
) else (
    echo   [api] Already running.
)

rem --- Start the UI, unless port 5173 is already listening -----------
netstat -ano | findstr /r /c:"TCP.*:5173 .*LISTENING" >nul
if errorlevel 1 (
    echo   [ui]  Starting the frontend on port 5173...
    start "English Coach UI" /min cmd /c "cd /d "%~dp0frontend" && npm run dev"
) else (
    echo   [ui]  Already running.
)

rem --- Wait until the UI actually answers, then open the browser -----
echo   [..]  Waiting for the app to come up...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "for ($i = 0; $i -lt 60; $i++) { try { Invoke-WebRequest 'http://localhost:5173' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 700 } }; exit 1"

if errorlevel 1 (
    echo.
    echo   The app did not respond in time.
    echo   Check the two minimised windows named "English Coach API" and
    echo   "English Coach UI" for the error, then try again.
    echo.
    pause
    exit /b 1
)

start "" "http://localhost:5173"
echo.
echo   Ready. The app is open in your browser.
echo   Leave the two minimised windows running while you study.
echo   Run stop.bat when you are finished.
echo.
ping -n 5 127.0.0.1 >nul
exit /b 0

:nopython
echo.
echo   Python was not found on your PATH.
echo   Install Python 3.12 or newer from https://python.org and tick
echo   "Add python.exe to PATH" during installation, then run this again.
echo.
pause
exit /b 1

:failed
echo.
echo   Setup failed. The error above says why.
echo.
pause
exit /b 1
