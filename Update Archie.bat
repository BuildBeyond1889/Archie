@echo off
title Archie - yearly update
cd /d "%~dp0"
where ollama >nul 2>nul || set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
echo ============================================
echo   Archie's yearly update
echo   Re-downloads the newest version of each model you already have.
echo   Needs the internet. Archie can stay open.
echo ============================================
echo.

curl -s -o nul -m 15 https://ollama.com
if errorlevel 1 (
  echo You don't seem to be online right now. Connect to the internet and run this again.
  echo Nothing was changed.
  echo.
  pause
  exit /b 1
)

ollama list >nul 2>nul || (start "" /min ollama serve & timeout /t 5 /nobreak >nul)
ollama list >nul 2>nul
if errorlevel 1 (
  echo Ollama isn't running and couldn't be started. Open Ollama from the Start menu, then run this again.
  echo.
  pause
  exit /b 1
)

echo Your models right now:
ollama list
echo.

set "FAILED="
for /f "skip=1 tokens=1" %%m in ('ollama list') do (
  echo --------------------------------------------
  echo Updating %%m ...
  ollama pull %%m || set "FAILED=1"
  echo.
)

echo ============================================
if defined FAILED (
  echo Some models didn't update ^(see above^). The old versions still work.
  echo Run this again later to retry.
) else (
  for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do (echo %%d)> "%~dp0last_update.txt"
  echo Done! All models are up to date. Archie will remind you again in a year.
)
echo.
echo Not touched on purpose:
echo  - The image maker, voice and Python add-ons. Updating those can break things
echo    ^(like the NumPy problem we fixed^), and the versions you have work.
echo  - Your offline Wikipedia. For a newer copy, run Get Wikipedia.bat.
echo  - Ollama itself updates on its own: when it has one ready, its tray icon
echo    says "Restart to update".
echo.
echo Want to look for NEWER models too? Every year or so, better small models come out.
echo Look for ones about 7-8B in size ^(that's what fits your 8 GB graphics card^).
choice /c YN /m "Open Ollama's model library in your browser"
if errorlevel 2 goto :end
start "" https://ollama.com/library
echo.
echo To try one:  ollama pull ^<name^>   then pick it from the model pill at the top of Archie.
echo Your old models stay installed, so you can always switch back.
:end
echo.
pause
