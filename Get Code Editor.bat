@echo off
title Archie - code editor (VSCodium) and coding tools
cd /d "%~dp0"
echo ============================================================
echo   Archie's coding setup
echo   - VSCodium: the open-source build of VS Code, no tracking
echo   - Continue: offline AI chat and autocomplete in the editor
echo   - Archie Coach: links VSCodium to Archie's Workshop
echo   - the coding models (about 6 GB if you don't have them)
echo   Then, if you want them, more languages.
echo ============================================================
echo.
where winget >nul 2>nul || (
  echo This needs winget ^(the Windows package installer^). Get "App Installer" from the Microsoft Store, then run this again.
  echo Or install VSCodium yourself from https://vscodium.com and run this again.
  pause
  exit /b
)

echo [1/5] VSCodium...
set "COD="
if exist "%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd" set "COD=%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd"
if exist "%ProgramFiles%\VSCodium\bin\codium.cmd" set "COD=%ProgramFiles%\VSCodium\bin\codium.cmd"
if not defined COD (
  winget install -e --id VSCodium.VSCodium --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd" set "COD=%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd"
  if exist "%ProgramFiles%\VSCodium\bin\codium.cmd" set "COD=%ProgramFiles%\VSCodium\bin\codium.cmd"
)
if not defined COD (
  echo VSCodium didn't install. Get it from https://vscodium.com and run this again.
  pause
  exit /b
)
echo   VSCodium is at %COD%
echo.

echo [2/5] Add-ons for VSCodium...
call "%COD%" --install-extension Continue.continue
call "%COD%" --install-extension "%~dp0World\workshop\archie-coach.vsix" --force
echo.

echo [3/5] Coding models...
where ollama >nul 2>nul || set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
ollama list >nul 2>nul || (start "" /min ollama serve & timeout /t 5 /nobreak >nul)
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:1.5b
echo.

echo [4/5] Settings...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0World\workshop\setup-settings.ps1" -ArchieFolder "%~dp0."
echo.

echo [5/5] More languages (Python is already here). Answer y or n for each:
choice /c yn /m "  JavaScript outside the browser (Node.js)"
if not errorlevel 2 winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
choice /c yn /m "  Java (Temurin JDK 21)"
if not errorlevel 2 winget install -e --id EclipseAdoptium.Temurin.21.JDK --accept-package-agreements --accept-source-agreements
choice /c yn /m "  C and C++ (the GCC compiler, WinLibs)"
if not errorlevel 2 winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT --accept-package-agreements --accept-source-agreements
choice /c yn /m "  C# (.NET 8 SDK)"
if not errorlevel 2 winget install -e --id Microsoft.DotNet.SDK.8 --accept-package-agreements --accept-source-agreements
choice /c yn /m "  Godot game engine (GDScript)"
if not errorlevel 2 winget install -e --id GodotEngine.GodotEngine --accept-package-agreements --accept-source-agreements
choice /c yn /m "  Arduino command-line tools (arduino-cli)"
if not errorlevel 2 winget install -e --id ArduinoSA.CLI --accept-package-agreements --accept-source-agreements
echo.
echo Done! Restart Archie so the Workshop sees the new tools,
echo then open it from the owl menu: Workshop (code with Archie).
echo In VSCodium, the Continue panel is the chat (Ctrl+L), and the eye at the bottom right is Archie Coach.
pause
