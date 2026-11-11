@echo off
REM Starts Archie Lite. If it's installed on this laptop, the installed copy runs; otherwise this one.
if exist "%LOCALAPPDATA%\ArchieLite\Start Archie Lite.bat" (
  call "%LOCALAPPDATA%\ArchieLite\Start Archie Lite.bat"
  exit /b
)
set "APPDIR=%~dp0"
cd /d "%APPDIR%"
if exist "%USERPROFILE%\anaconda3\pythonw.exe" (
  start "" "%USERPROFILE%\anaconda3\pythonw.exe" "%APPDIR%app\lite.py"
  exit /b
)
where pythonw >nul 2>nul && (start "" pythonw "%APPDIR%app\lite.py" & exit /b)
where pyw >nul 2>nul && (start "" pyw "%APPDIR%app\lite.py" & exit /b)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\pythonw.exe" (start "" "%%D\pythonw.exe" "%APPDIR%app\lite.py" & exit /b)
echo Python isn't installed. Run "Install or Update Archie Lite.bat" instead.
pause
