@echo off
REM lives in Archie\Tools: ARCHIE is the Archie folder one level up
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
title Archie - image maker test
cd /d "%ARCHIE%"
set "HF_HUB_OFFLINE=1"
set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
echo ============================================
echo   Testing the image maker step by step. Leave this open.
echo   Close Archie first so nothing else is using the graphics card.
echo ============================================
echo.
"%PY%" "%ARCHIE%archie_imagine.py" --test
echo.
echo Send Claude a screenshot of this window.
pause
