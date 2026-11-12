@echo off
REM lives in Archie\Tools: ARCHIE is the Archie folder one level up
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
title Archie - fast talk
cd /d "%ARCHIE%"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "HF_HUB_VERBOSITY=error"
set "HF_HUB_DISABLE_TELEMETRY=1"
echo ============================================
echo   Faster talk mode (Ctrl+Alt+T)
echo   - a quick speech model just for talk mode (base.en, about 150 MB)
echo   - optional: a quick chat model for talk mode (qwen2.5:3b, about 2 GB)
echo   Needs the internet once. Archie can stay open.
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
echo [1/2] Downloading the quick speech model...
"%PY%" -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8', download_root=r'%ARCHIE%Voice'); print('Speech model ready.')"
echo.
echo [2/2] The quick chat model for talk mode (optional, about 2 GB)?
choice /c YN /n /m "Download qwen2.5:3b now? Y or N: "
if errorlevel 2 goto done
ollama pull qwen2.5:3b
if errorlevel 1 (
  echo Couldn't download it. Is the Ollama app running?
  pause
  exit /b
)
echo.
echo Downloaded. Turn it on in Archie: right-click the owl ^> Voice ^& quiet settings ^>
echo "Quick talk model".

:done
echo.
echo Done! Restart Archie, then Ctrl+Alt+T to talk.
pause
