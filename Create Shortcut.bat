@echo off
REM Puts an "Archie" shortcut with the owl icon on your Desktop and in the Start menu.
REM The shortcut starts Python directly (not a .bat), so Windows lets you pin it to the taskbar.
cd /d "%~dp0"
set "PYW="
if exist "%USERPROFILE%\anaconda3\pythonw.exe" set "PYW=%USERPROFILE%\anaconda3\pythonw.exe"
if not defined PYW for /f "delims=" %%P in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%P"
if not defined PYW (
  echo Could not find pythonw.exe. Is Python / Anaconda installed?
  pause
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {" ^
  "  $s = $ws.CreateShortcut((Join-Path $dir 'Archie.lnk'));" ^
  "  $s.TargetPath = '%PYW%';" ^
  "  $s.Arguments = '\"%~dp0archie.py\"';" ^
  "  $s.WorkingDirectory = '%~dp0';" ^
  "  $s.IconLocation = '%~dp0archie.ico,0';" ^
  "  $s.Description = 'Archie - your offline AI';" ^
  "  $s.Save() }"
echo.
echo Done! The Archie owl is on your Desktop and in the Start menu.
echo.
echo TO PIN IT TO THE TASKBAR (Windows won't let programs do this themselves):
echo   Start menu ^> find Archie ^> right-click ^> Pin to taskbar
echo   (or right-click the Desktop icon ^> Show more options ^> Pin to taskbar)
echo.
echo Clicking the taskbar owl starts Archie, or pops the chat open if it's already running.
echo If you pinned the OLD shortcut before, unpin it first, then pin this one.
pause
