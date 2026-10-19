@echo off
setlocal
title Archie - get offline Wikipedia
cd /d "%~dp0"
if not exist "Wikipedia" mkdir "Wikipedia"
echo ============================================
echo   Offline Wikipedia for Archie
echo ============================================
echo.
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "[math]::Round((Get-PSDrive -Name ('%~d0'.Substring(0,1))).Free/1GB)"`) do set FREE=%%F
echo Free space on drive %~d0  about %FREE% GB
echo.
echo Pick one:
echo   1) Every article, text only, no pictures ....... 49 GB   (best)
echo   2) Every article, just the intro section ...... 13 GB
echo   3) The ~50,000 most popular articles, text .... 2.6 GB  (quick to try)
echo   4) Cancel
echo.
choice /c 1234 /n /m "Your choice (1-4): "
if errorlevel 4 exit /b
if errorlevel 3 (set "FILE=wikipedia_en_top_nopic_2026-09.zim" & goto go)
if errorlevel 2 (set "FILE=wikipedia_en_all_mini_2026-09.zim" & goto go)
set "FILE=wikipedia_en_all_nopic_2026-06.zim"
:go
set "URL=https://download.kiwix.org/zim/wikipedia/%FILE%"
set "OUT=Wikipedia\%FILE%"
echo.
echo Downloading %FILE%
echo into %~dp0Wikipedia
echo.
echo This can take hours for the big ones. You can close this window anytime:
echo run this file again and pick the same number to resume where it stopped.
echo.
curl.exe -L -C - --retry 5 --retry-delay 10 -o "%OUT%.part" "%URL%"
if errorlevel 1 (
  echo.
  echo The download stopped. Run this again and pick the same number to resume.
  echo If it keeps failing, the file name may have changed: check kiwix.org for the newest
  echo "wikipedia_en" file and put it in the Wikipedia folder yourself.
  pause
  exit /b
)
move /y "%OUT%.part" "%OUT%" >nul
echo.
echo Done! Wikipedia is ready. In Archie, click the Wiki button so it turns teal.
echo (If you downloaded a bigger one later, you can delete the smaller .zim file.)
pause
