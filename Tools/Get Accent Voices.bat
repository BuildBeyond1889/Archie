@echo off
REM lives in Archie\Tools: ARCHIE is the Archie folder one level up
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
title Archie - accent voices (audition)
cd /d "%ARCHIE%"
echo ============================================
echo   Archie's accent voices: Irish woman, Irish man, Londoner
echo   - about 4 GB in all: its own Python with PyTorch (Voice\clone), the voice model
echo     (Chatterbox Turbo, MIT licence) and short reference recordings from the VCTK
echo     corpus (University of Edinburgh, CC BY 4.0: people who recorded for open research)
echo   - runs on your graphics card, offline once this is done
echo   Needs the internet now. QUIT ARCHIE FIRST (right-click the owl, Quit).
echo ============================================
echo.
set "PY="
where py >nul 2>nul && (py -3.11 -c "1" >nul 2>nul && set "PY=py -3.11")
if not defined PY (where py >nul 2>nul && (py -3.12 -c "1" >nul 2>nul && set "PY=py -3.12"))
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo This needs Python 3.11 or 3.12. Install Python 3.11 from python.org ^(tick "Add to PATH"^), then run this again.
  pause
  exit /b
)
set "C=%ARCHIE%Voice\clone"
if not exist "%C%" mkdir "%C%"
echo [1/4] Its own Python setup, so nothing else in Archie changes...
if not exist "%C%\env\Scripts\python.exe" %PY% -m venv "%C%\env"
if not exist "%C%\env\Scripts\python.exe" (
  echo Couldn't make it. Tell Claude what this window says.
  pause
  exit /b
)
set "E=%C%\env\Scripts\python.exe"
echo.
echo [2/4] PyTorch for your graphics card (about 2.5 GB)...
"%E%" -m pip install --upgrade pip >nul
"%E%" -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
if errorlevel 1 (
  echo PyTorch didn't install. Tell Claude what this window says.
  pause
  exit /b
)
echo.
echo [3/4] The voice model's add-ons...
"%E%" -m pip install chatterbox-tts==0.1.7 remotezip soundfile
if errorlevel 1 (
  echo The add-ons didn't install. Tell Claude what this window says.
  pause
  exit /b
)
echo.
echo [4/4] Reference recordings and the audition (a few minutes)...
"%E%" -s "%ARCHIE%archie_accents.py" fetch
if errorlevel 1 goto whole
if not exist "%ARCHIE%Voice\accents\accents.json" goto whole
goto done

:whole
echo.
echo The recordings server wouldn't hand over just the few files needed.
echo The other way is to download the whole corpus once (about 11 GB), take the few
echo recordings out, and delete the rest.
set /p OK=Download the whole thing now? Type Y and press Enter (anything else stops):
if /i not "%OK%"=="Y" (
  echo Stopped. Nothing else was changed.
  pause
  exit /b
)
if not exist "%ARCHIE%Voice\accents" mkdir "%ARCHIE%Voice\accents"
curl -L --fail -o "%ARCHIE%Voice\accents\VCTK-Corpus-0.92.zip" https://datashare.is.ed.ac.uk/bitstream/handle/10283/3443/VCTK-Corpus-0.92.zip
"%E%" -s "%ARCHIE%archie_accents.py" fetch "%ARCHIE%Voice\accents\VCTK-Corpus-0.92.zip"
if exist "%ARCHIE%Voice\accents\accents.json" del "%ARCHIE%Voice\accents\VCTK-Corpus-0.92.zip"
if not exist "%ARCHIE%Voice\accents\accents.json" (
  echo The audition couldn't be made. Tell Claude what this window says.
  pause
  exit /b
)

:done
echo.
echo Done! Start Archie, right-click the owl ^> Voice ^& quiet settings:
echo the accent voices now say "audition". Click one, play each voice, and pick the one you like.
pause
