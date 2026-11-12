@echo off
REM lives in Archie\Tools: ARCHIE is the Archie folder one level up
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
title Archie - Sonia
cd /d "%ARCHIE%"
echo ============================================
echo   Sonia for Archie (Microsoft's natural British voice)
echo   - a few MB of add-ons in the voice's own Python (Voice\kokoro\env)
echo   - Sonia needs the internet each time she talks: what Archie says
echo     goes to Microsoft to be spoken. Offline, Archie uses the
echo     British woman voice instead, on its own.
echo   Run Get Archie Voice.bat first if you haven't. QUIT ARCHIE FIRST.
echo ============================================
echo.
set "K=%ARCHIE%Voice\kokoro"
if not exist "%K%\env\Scripts\python.exe" (
  echo Archie's voice isn't set up yet. Run Tools\Get Archie Voice.bat first, then this.
  pause
  exit /b
)
echo [1/2] Installing Sonia's add-ons...
"%K%\env\Scripts\python.exe" -m pip install --upgrade edge-tts miniaudio
echo.
echo [2/2] A quick test (Sonia says hello)...
"%K%\env\Scripts\python.exe" -s "%ARCHIE%archie_voiced.py" --test-sonia
if errorlevel 1 (
  echo.
  echo The test didn't work. Check the internet, or tell Claude what this window says.
  pause
  exit /b
)
echo.
echo Done! Start Archie, right-click the owl ^> Voice ^& quiet settings ^> pick "Sonia".
pause
