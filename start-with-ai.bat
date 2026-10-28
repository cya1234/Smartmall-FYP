@echo off
title SmartMall - web + AI services (CLIP + Prophet + CatVTON)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   [x] Python venv not found at .venv\
  echo       Run the one-time setup in README.md first.
  echo.
  pause
  exit /b 1
)

set MPLCONFIGDIR=%~dp0.cache\mpl
set HF_HOME=%~dp0.cache\hf

echo.
echo   Starting CLIP visual-search service on port 8001 ...
start "SmartMall CLIP service" cmd /k ".venv\Scripts\python.exe ai-service\visual_search_service.py --port 8001"

echo   Starting Prophet price-forecast service on port 8002 ...
start "SmartMall Prophet service" cmd /k ".venv\Scripts\python.exe ai-service\forecast_service.py --port 8002"

if exist "data\models\instruct-pix2pix-fp16\unet\diffusion_pytorch_model.safetensors" (
  echo   Starting CatVTON try-on service on port 8003 ...
  start "SmartMall CatVTON service" cmd /k ".venv\Scripts\python.exe ai-service\tryon_service.py --port 8003"
) else (
  echo.
  echo   [!] CatVTON weights not prepared - try-on will use the overlay preview.
  echo       Enable real try-on with:
  echo         .venv\Scripts\python.exe tools\prepare_catvton_base.py
  echo.
)

echo   Waiting for the models to load ...
timeout /t 18 /nobreak >nul

echo   Starting the web server on port 3000 ...
echo.
echo   Keep ALL service windows open while the site is in use.
echo   Any service that is closed degrades gracefully:
echo     CLIP off    -^> colour-based visual search
echo     Prophet off -^> linear trend forecast
echo     CatVTON off -^> colour overlay try-on preview
echo.
node server.js

echo.
echo   Web server stopped. Close the service windows too.
pause
