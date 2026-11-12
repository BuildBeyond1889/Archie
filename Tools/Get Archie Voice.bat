@echo off
REM lives in Archie\Tools: ARCHIE is the Archie folder one level up
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
title Archie - the new voice
cd /d "%ARCHIE%"
echo ============================================
echo   Archie's new voice (Kokoro), all offline once this is done
echo   - about 350 MB: the voice model and its own small Python setup
echo   - it lives in Voice\kokoro and doesn't change anything else in Archie
echo   Needs the internet once. QUIT ARCHIE FIRST (right-click the owl, Quit).
echo ============================================
echo.
set "PY="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (where py >nul 2>nul && set "PY=py")
if not defined PY (
  echo Could not find Python.
  pause
  exit /b
)
set "K=%ARCHIE%Voice\kokoro"
if not exist "%K%" mkdir "%K%"

"%PY%" -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)"
if errorlevel 1 (
  echo This Python is too old or too new for the voice ^(it needs 3.10 to 3.13^).
  "%PY%" --version
  echo Install Python 3.12 from python.org ^(tick "Add to PATH"^), then run this again.
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%PY%" -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)"
  if errorlevel 1 (
    pause
    exit /b
  )
)

echo [1/4] Making the voice its own Python setup (so nothing else in Archie changes)...
if not exist "%K%\env\Scripts\python.exe" "%PY%" -m venv "%K%\env"
if not exist "%K%\env\Scripts\python.exe" (
  echo Couldn't make it. Tell Claude what this window says.
  pause
  exit /b
)
echo.
echo [2/4] Installing the voice add-ons...
"%K%\env\Scripts\python.exe" -m pip install --upgrade pip >nul
"%K%\env\Scripts\python.exe" -m pip install --upgrade kokoro-onnx sounddevice scipy
echo.
echo [3/4] Downloading the voice (about 350 MB)...
if not exist "%K%\kokoro-v1.0.onnx" curl -L --fail -o "%K%\kokoro-v1.0.onnx" https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
if not exist "%K%\voices-v1.0.bin" curl -L --fail -o "%K%\voices-v1.0.bin" https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
echo.
echo [4/4] A quick test (Archie says hello)...
set "ARCHIE_KOKORO_DIR=%K%"
"%K%\env\Scripts\python.exe" -s -c "import os,numpy as np,sounddevice as sd;from kokoro_onnx import Kokoro;d=os.environ['ARCHIE_KOKORO_DIR'];k=Kokoro(d+r'\kokoro-v1.0.onnx',d+r'\voices-v1.0.bin');s=k.get_voice_style('bm_george')*0.6+k.get_voice_style('bm_fable')*0.4;a,sr=k.create('Hello. This is my new voice. Shall we get started?',voice=s,speed=0.95,lang='en-gb');sd.play(a,sr);sd.wait();print('Voice works.')"
if errorlevel 1 (
  echo.
  echo The test didn't work. Tell Claude what this window says.
  pause
  exit /b
)
echo.
echo Done! Start Archie, then:
echo   Ctrl+Alt+T       talk mode: just talk, cut in any time, Esc to end
echo   Ctrl+Alt+Q       mute / unmute (captions instead of sound)
echo   Right-click the owl ^> Voice ^& quiet settings   pick the voice, speed, pronunciations, Quiet
pause
