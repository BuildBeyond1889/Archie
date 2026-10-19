@echo off
title Vault Check
cd /d "%~dp0"
echo Vault Check tests search on your real library and writes a report for Claude.
echo It only reads the library. Leave this window open: it takes about 15 to 40 minutes.
echo.
if exist "%USERPROFILE%\anaconda3\python.exe" (
  "%USERPROFILE%\anaconda3\python.exe" vault_check.py
) else (
  python vault_check.py
)
pause
