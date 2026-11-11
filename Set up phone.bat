@echo off
title Set up Archie on your phone
REM Gives this PC a private https address on your Tailscale network for the Archie phone app.
REM Only devices signed in to your Tailscale account can open it. Run once (Windows asks for admin).
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if not exist "%TS%" (
  echo Tailscale isn't installed on this PC.
  pause
  exit /b 1
)
echo Turning on the phone address (Tailscale serve, https, your tailnet only)...
"%TS%" serve --bg 47330
if errorlevel 1 (
  echo.
  echo If it says HTTPS or Serve isn't enabled: open the link it shows, allow it, then run this again.
  pause
  exit /b 1
)
for /f "delims=" %%U in ('powershell -NoProfile -Command "((& '%TS%' status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')"') do set "HOST=%%U"
echo https://%HOST%| clip
echo.
echo   Your phone app:  https://%HOST%
echo   (copied: paste it into a message to yourself)
echo.
echo On your phone:
echo   1. Install Tailscale from the Play Store and sign in with the same account.
echo   2. Open the address above in Chrome.
echo   3. Chrome menu (three dots) ^> Install app. Then open Archie from the home screen.
echo   4. In Archie: More ^> Settings ^> turn on notifications.
echo.
echo Archie on this PC must be running (and restarted once after this update).
pause
