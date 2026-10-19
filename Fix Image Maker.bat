@echo off
title Archie - fixing the image maker
cd /d "%~dp0"
echo ============================================
echo   Fixing a version clash: a newer NumPy (2.x) got installed, but Anaconda's
echo   SciPy was built for NumPy 1.x, so the image libraries crash when loading.
echo   This puts NumPy back to the 1.x version Anaconda expects.
echo   CLOSE ARCHIE FIRST. Needs the internet for a minute.
echo ============================================
echo.
set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m pip install "numpy<2" --only-binary=:all:
if errorlevel 1 (
  echo.
  echo NumPy 1.x isn't available for this Python, so updating SciPy to match NumPy 2 instead...
  "%PY%" -m pip install --upgrade scipy --only-binary=:all:
)
echo.
echo Now testing the image maker again...
echo.
set "HF_HUB_OFFLINE=1"
"%PY%" "%~dp0archie_imagine.py" --test
echo.
echo If it says DONE, start Archie and try:  draw a cat sitting on a stack of books
echo If not, send Claude a screenshot of this window.
pause
