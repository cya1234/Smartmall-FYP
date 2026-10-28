@echo off
title SmartMall server - keep this window open while friends use the site
cd /d "%~dp0"

echo.
echo   Starting SmartMall...
echo   Keep this window OPEN - closing it stops the website.
echo.

node server.js

echo.
echo   Server stopped.
pause
