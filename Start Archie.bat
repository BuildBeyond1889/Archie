@echo off
REM Double-click to start Archie with no console window.
cd /d "%~dp0"
if exist "%USERPROFILE%\anaconda3\pythonw.exe" (
  start "" "%USERPROFILE%\anaconda3\pythonw.exe" archie.py
  exit /b
)
where pythonw >nul 2>nul && (start "" pythonw archie.py & exit /b)
where pyw >nul 2>nul && (start "" pyw archie.py & exit /b)
echo Could not find Python. Open Anaconda Prompt and run: python archie.py
pause
