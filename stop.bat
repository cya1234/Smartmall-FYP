@echo off
setlocal enabledelayedexpansion
title SmartMall - stop all services
cd /d "%~dp0"

echo.
echo   Stopping SmartMall services ...
echo.

set FOUND=0
for %%P in (3000 8001 8002 8003) do (
  set "HIT="
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    set "HIT=1"
    echo   port %%P  -  stopping pid %%A
    taskkill /F /PID %%A >nul 2>&1
  )
  if not defined HIT echo   port %%P  -  nothing running
)

echo.
echo   Checking ...
timeout /t 2 /nobreak >nul

set LEFT=0
for %%P in (3000 8001 8002 8003) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    echo   port %%P still listening on pid %%A
    set LEFT=1
  )
)
if "!LEFT!"=="0" echo   all ports free - the site is off.

echo.
echo   If you opened a Cloudflare tunnel window, close that one too --
echo   otherwise the public URL keeps pointing at a machine with nothing on it.
echo.
echo   GPU memory now:
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>nul
echo.
echo   (Some memory is always in use by Chrome, Discord, Steam and so on.
echo    What matters is that the number drops back to the usual baseline.)
echo.
pause
