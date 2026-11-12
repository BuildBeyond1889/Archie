@echo off
REM Puts Ollama back to its own defaults and restarts it.
reg delete HKCU\Environment /v OLLAMA_FLASH_ATTENTION /f >nul 2>nul
reg delete HKCU\Environment /v OLLAMA_KV_CACHE_TYPE /f >nul 2>nul
reg delete HKCU\Environment /v OLLAMA_NUM_PARALLEL /f >nul 2>nul
taskkill /f /im "ollama app.exe" >nul 2>nul
taskkill /f /im ollama.exe >nul 2>nul
timeout /t 3 /nobreak >nul
set "OLLAMA_FLASH_ATTENTION="
set "OLLAMA_KV_CACHE_TYPE="
set "OLLAMA_NUM_PARALLEL="
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe") else (start "" /min ollama serve)
echo Ollama is back to its defaults. Restart Archie too.
pause
