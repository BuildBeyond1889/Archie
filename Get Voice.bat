@echo off
title Archie - voice notes
cd /d "%~dp0"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "HF_HUB_VERBOSITY=error"
set "HF_HUB_DISABLE_TELEMETRY=1"
echo ============================================
echo   Archie voice notes (all offline once this is done)
echo   - microphone recording
echo   - Whisper, which types out what you say
echo   - Piper, so Archie can talk back (4 voices, about 350 MB)
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
echo Which speech model?
echo   1 = small.en   about 480 MB, fast, very good (recommended)
echo   2 = medium.en  about 1.5 GB, a bit more accurate, about 2-3x slower
choice /c 12 /n /m "Press 1 or 2: "
if errorlevel 2 (set "M=medium.en") else (set "M=small.en")
echo.
echo [1/4] Installing the recording, Whisper and Piper add-ons...
"%PY%" -m pip install --upgrade faster-whisper sounddevice piper-tts "numpy<2"
echo.
echo [2/4] Downloading the %M% speech model...
"%PY%" -c "from faster_whisper import WhisperModel; WhisperModel('%M%', device='cpu', compute_type='int8', download_root=r'%~dp0Voice'); print('Model ready.')"
echo.
echo [3/4] Downloading Archie's speaking voices...
if not exist "%~dp0Voice\piper" mkdir "%~dp0Voice\piper"
"%PY%" -m piper.download_voices en_GB-alan-medium en_US-ryan-high en_US-lessac-medium en_GB-jenny_dioco-medium --download-dir "%~dp0Voice\piper"
echo.
echo [4/4] Telling Archie to use it...
"%PY%" -c "import json,os; p=r'%~dp0archie_config.json'; c=json.load(open(p)) if os.path.exists(p) else {}; c['voice_model']='%M%'; json.dump(c, open(p,'w'), indent=2); print('Set voice_model =', c['voice_model'])"
echo.
echo Done! Start Archie, then:
echo   mic  (Ctrl+Alt+V)   record a voice note
echo   Ctrl+Alt+T          talk to Archie; press again to send, and it answers out loud
echo   speak               read every answer out loud
echo   Right-click the owl ^> Archie's voice  to pick a different voice.
echo Tip: if the mic doesn't work, open Windows Settings ^> Privacy ^& security ^>
echo Microphone and turn on "Let desktop apps access your microphone".
pause
