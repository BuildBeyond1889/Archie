@echo off
title Archie - downloading models
where ollama >nul 2>nul || set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
ollama list >nul 2>nul || (start "" /min ollama serve & timeout /t 5 /nobreak >nul)
echo ============================================
echo   Downloading Archie's models (about 13 GB total)
echo   This can take a while. Leave this window open.
echo ============================================
echo.
echo [1/3] qwen2.5:7b  - main model for school and general help
ollama pull qwen2.5:7b
echo.
echo [2/3] qwen2.5-coder:7b  - programming
ollama pull qwen2.5-coder:7b
echo.
echo [3/3] gemma3:4b  - reads images (photos of notes, screenshots)
ollama pull gemma3:4b
echo.
echo Installed models:
ollama list
echo.
echo Done! Click the owl and pick qwen2.5:7b from the dropdown at the top.
pause
