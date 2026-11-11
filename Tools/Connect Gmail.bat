@echo off
REM Connect your Gmail to Archie: you type the Gmail app password in the window (it is encrypted and stays on this PC).
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
cd /d "%ARCHIE%"
if exist "%USERPROFILE%\anaconda3\pythonw.exe" (
  start "" "%USERPROFILE%\anaconda3\pythonw.exe" archie_mail.py --setup
  exit /b
)
where pythonw >nul 2>nul && (start "" pythonw archie_mail.py --setup & exit /b)
python archie_mail.py --setup
pause
