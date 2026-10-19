@echo off
title Archie - installing extras
cd /d "%~dp0"
echo ============================================
echo   Installing Archie's extras
echo   - PDF and Word reading
echo   - drag-and-drop files onto the chat
echo   - offline Wikipedia search
echo   - the notes-search model (nomic-embed-text)
echo ============================================
echo.
set "PY="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (where py >nul 2>nul && set "PY=py")
if not defined PY (
  echo Could not find Python.
  pause
  exit /b
)
echo [1/2] Python add-ons...
"%PY%" -m pip install --upgrade pypdf python-docx tkinterdnd2 libzim pillow-heif
echo.
echo [2/2] Notes-search model (about 270 MB)...
where ollama >nul 2>nul || set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
ollama pull nomic-embed-text
echo.
echo Done! If Archie is open, right-click the owl, Quit, and start it again.
pause
