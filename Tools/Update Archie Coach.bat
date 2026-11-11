@echo off
REM lives in Archie\Tools: ARCHIE is the Archie folder one level up
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
title Archie - updating the Archie Coach add-on
cd /d "%ARCHIE%"
set "COD="
if exist "%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd" set "COD=%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd"
if exist "%ProgramFiles%\VSCodium\bin\codium.cmd" set "COD=%ProgramFiles%\VSCodium\bin\codium.cmd"
if not defined COD (
  echo VSCodium isn't installed. Run Get Code Editor.bat first.
  pause
  exit /b
)
call "%COD%" --install-extension "%ARCHIE%World\workshop\archie-coach.vsix" --force
echo.
echo Done. In VSCodium press Ctrl+Shift+P, type "reload window" and press Enter.
pause
