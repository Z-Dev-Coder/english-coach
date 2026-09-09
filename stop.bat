@echo off
rem Stops the English Coach servers by closing whatever is listening on
rem ports 8000 and 5173. Other Python and Node processes are left alone.
setlocal enabledelayedexpansion
title Stopping English Coach

echo.
echo   Stopping English Coach...

for %%P in (8000 5173) do (
    set "found="
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:"TCP.*:%%P .*LISTENING"') do (
        if not "%%A"=="0" (
            taskkill /f /pid %%A >nul 2>&1
            set "found=1"
        )
    )
    if defined found (
        echo   [%%P] Stopped.
    ) else (
        echo   [%%P] Was not running.
    )
)

rem Close the launcher's console windows if they are still open.
taskkill /f /fi "WINDOWTITLE eq English Coach API*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq English Coach UI*" >nul 2>&1

echo   Done.
ping -n 3 127.0.0.1 >nul
