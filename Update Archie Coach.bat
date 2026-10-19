@echo off
title Archie - updating the Archie Coach add-on
cd /d "%~dp0"
set "COD="
if exist "%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd" set "COD=%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd"
if exist "%ProgramFiles%\VSCodium\bin\codium.cmd" set "COD=%ProgramFiles%\VSCodium\bin\codium.cmd"
if not defined COD (
  echo VSCodium isn't installed. Run Get Code Editor.bat first.
  pause
  exit /b
)
call "%COD%" --install-extension "%~dp0World\workshop\archie-coach.vsix" --force
echo.
echo Done. In VSCodium press Ctrl+Shift+P, type "reload window" and press Enter.
pause
