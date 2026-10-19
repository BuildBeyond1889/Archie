@echo off
title Archie - handwriting reader
cd /d "%~dp0"
echo ============================================
echo   Archie's handwriting reader
echo   - qwen2.5vl:7b : reads handwriting and printed pages (about 6 GB)
echo   - pillow-heif  : lets Archie open iPhone photos (.heic)
echo   Needs the internet once. Leave this window open.
echo ============================================
echo.
where ollama >nul 2>nul || set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
ollama list >nul 2>nul || (start "" /min ollama serve & timeout /t 5 /nobreak >nul)
echo [1/2] Downloading the handwriting model...
ollama pull qwen2.5vl:7b
echo.
set "PY="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (where py >nul 2>nul && set "PY=py")
echo [2/2] iPhone photo support...
if defined PY ("%PY%" -m pip install --upgrade pillow-heif) else (echo Could not find Python - skipped.)
echo.
echo Done! Restart Archie (right-click the owl, Quit, then start it again).
echo Archie now reads any photo of notes you put in the Notes folder by itself.
pause
