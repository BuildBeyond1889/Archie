@echo off
title Archie Lite installer
REM Installs Archie Lite on this laptop, or updates it. Safe to run again: your data is kept.
cd /d "%~dp0"
set "PY="

call :try py -3
if not defined PY call :try python
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" call :try "%USERPROFILE%\anaconda3\python.exe"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" call :try "%%D\python.exe"
if defined PY goto run

echo.
echo   Python isn't on this laptop yet. Installing Python 3.12 for you (one time, about a minute)...
where winget >nul 2>nul && winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" call :try "%%D\python.exe"
if defined PY goto run
echo.
echo   Couldn't install Python automatically. Opening python.org: install Python 3,
echo   tick "Add python.exe to PATH", then run this file again.
start "" https://www.python.org/downloads/windows/
pause
exit /b 1

:run
%PY% "%~dp0installer\install.py"
echo.
pause
exit /b

:try
%* -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>nul && set "PY=%*"
exit /b
