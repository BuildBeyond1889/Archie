@echo off
title Archie - image maker test
cd /d "%~dp0"
set "HF_HUB_OFFLINE=1"
set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
echo ============================================
echo   Testing the image maker step by step. Leave this open.
echo   Close Archie first so nothing else is using the graphics card.
echo ============================================
echo.
"%PY%" "%~dp0archie_imagine.py" --test
echo.
echo Send Claude a screenshot of this window.
pause
