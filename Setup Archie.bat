@echo off
title Archie setup
cd /d "%~dp0"
echo ============================================
echo   Archie setup
echo ============================================
echo.

where ollama >nul 2>nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
  ) else (
    echo Could not find Ollama. Install it from ollama.com, then run this again.
    pause
    exit /b
  )
)

echo [1/4] Making sure Ollama is running...
ollama list >nul 2>nul
if errorlevel 1 (
  start "" /min ollama serve
  timeout /t 5 /nobreak >nul
)

echo [2/4] Downloading the starter model (about 1 GB, one time only)...
ollama pull qwen2.5:1.5b
if errorlevel 1 (
  echo.
  echo The download failed. Check your internet connection and run this again.
  pause
  exit /b
)

echo.
echo [3/4] Your graphics card:
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>nul || echo   (could not read it - that's OK)

echo.
echo [4/4] Starting Archie...
set "PY="
if exist "%USERPROFILE%\anaconda3\pythonw.exe" set "PY=%USERPROFILE%\anaconda3\pythonw.exe"
if not defined PY (where pythonw >nul 2>nul && set "PY=pythonw")
if not defined PY (where pyw >nul 2>nul && set "PY=pyw")
if not defined PY (
  echo Could not find Python. Open Anaconda Prompt, go to this folder, and run: python archie.py
  pause
  exit /b
)
start "" "%PY%" archie.py

echo.
echo Done! Look for the owl near the bottom-right of your screen.
echo From now on, just double-click "Start Archie.bat".
echo With 8 GB or more of graphics memory, run Get Models.bat for the bigger, smarter models.
echo.
pause
