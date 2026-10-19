@echo off
title Archie - LocalSend (phone to PC, no internet or account needed)
cd /d "%~dp0"
if not exist "Notes\Handwritten" mkdir "Notes\Handwritten"
echo ============================================
echo   Installing LocalSend on this PC (free, open source).
echo   It sends photos from your phone or Surface straight to this PC
echo   over your home Wi-Fi. Nothing goes through the internet.
echo ============================================
echo.
winget install --id LocalSend.LocalSend -e --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
  echo.
  echo winget couldn't install it. Opening the download page instead...
  start "" https://localsend.org/download
)
echo.
echo ============================================
echo   NOW SET IT UP (one time):
echo   1. Open LocalSend on this PC.  If Windows Firewall asks, click Allow
echo      (Private networks).
echo   2. Settings ^> Receive:
echo        - Destination: choose  %~dp0Notes\Handwritten
echo        - Quick Save: ON   (photos arrive without clicking Accept)
echo   3. Settings ^> General: turn on starting with Windows / start hidden
echo      so it's always ready.
echo   4. On your phone or Surface: install LocalSend (App Store / Google
echo      Play / Microsoft Store), be on the same Wi-Fi, tap Send, pick the
echo      photos, then tap this PC.
echo   Archie reads them within about a minute.
echo ============================================
echo.
echo Opening the folder photos will go to...
start "" "%~dp0Notes\Handwritten"
pause
