@echo off
title Make Archie Lite stick
REM Run on the PC. Copies the newest Archie Lite (app, panel, installer, pairing) to the stick.
REM Your laptop's data on the stick is left alone. Usage: double-click, or "Make Archie Lite stick.bat F"
setlocal
set "SRC=%~dp0"
set "DRV=%~1"
if not defined DRV set /p "DRV=Stick drive letter [E]: "
if not defined DRV set "DRV=E"
set "DRV=%DRV::=%"
if not exist "%DRV%:\" (
  echo No drive %DRV%: found. Plug the stick in and try again.
  pause
  exit /b 1
)
set "DST=%DRV%:\ArchieLite"
echo Copying Archie Lite to %DST% ...
robocopy "%SRC%app" "%DST%\app" /E /XD __pycache__ /XF *.pyc *.tmp *.new /NJH /NJS /NP /NDL >nul
robocopy "%SRC%web" "%DST%\web" /E /NJH /NJS /NP /NDL >nul
robocopy "%SRC%installer" "%DST%\installer" /E /XD __pycache__ /XF *.pyc /NJH /NJS /NP /NDL >nul
if not exist "%DST%\data" mkdir "%DST%\data"
if exist "%SRC%data\pairing.json" copy /y "%SRC%data\pairing.json" "%DST%\data\pairing.json" >nul
for %%F in ("Install or Update Archie Lite.bat" "Start Archie Lite.bat" "README.md") do copy /y "%SRC%%%~F" "%DST%\%%~F" >nul
echo Done. On the laptop: open %DRV%:\ArchieLite and double-click "Install or Update Archie Lite.bat".
pause
