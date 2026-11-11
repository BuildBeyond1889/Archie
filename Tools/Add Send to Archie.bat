@echo off
title Add "Send to Archie" to the right-click menu
REM Puts "Archie" in the right-click Send to menu. Run once. To remove it, delete "Archie" from
REM the folder that opens with Win+R -> shell:sendto
set "SENDTO=%APPDATA%\Microsoft\Windows\SendTo"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SENDTO%\Archie.lnk'); $s.TargetPath='%~dp0Send to Archie.bat'; $s.WindowStyle=7; $s.IconLocation='%~dp0..\archie.ico,0'; $s.Save()"
if exist "%SENDTO%\Archie.lnk" (
  echo Done. Right-click any file, then Send to, then Archie.
) else (
  echo Something went wrong: the shortcut wasn't made.
)
echo.
pause
