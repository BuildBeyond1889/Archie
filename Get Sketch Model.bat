@echo off
title Archie - sketch reader (for sketch to image)
cd /d "%~dp0"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "HF_HUB_VERBOSITY=error"
set "HF_HUB_DISABLE_TELEMETRY=1"
echo ============================================
echo   Sketch to image: downloads the sketch reader (a few hundred MB, into D:\Archie\Images).
echo   It lets the image maker follow the lines of your drawings.
echo   Needs the internet once. You need Get Image Maker.bat done first.
echo   QUIT ARCHIE FIRST (right-click the owl, Quit).
echo ============================================
echo.
set "PY="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Could not find Python.
  pause
  exit /b
)
"%PY%" "%~dp0archie_imagine.py" --download-sketch
echo.
echo Done! Start Archie, right-click the owl and pick "Sketch to image...",
echo or type  sketch  in the chat.
pause
