@echo off
REM Run once. Makes Ollama (Archie's brain) use less graphics memory and run cooler:
REM   flash attention + a compressed context cache (about half a GB less for the 7b, a little faster)
REM   one request at a time (Archie never needs more, and each extra slot holds memory)
REM Then restarts Ollama so it picks them up. To undo: Tools\Undo Ollama Cooler.bat
echo Setting Ollama to run cooler...
setx OLLAMA_FLASH_ATTENTION 1 >nul
setx OLLAMA_KV_CACHE_TYPE q8_0 >nul
setx OLLAMA_NUM_PARALLEL 1 >nul
echo Restarting Ollama...
taskkill /f /im "ollama app.exe" >nul 2>nul
taskkill /f /im ollama.exe >nul 2>nul
timeout /t 3 /nobreak >nul
set "OLLAMA_FLASH_ATTENTION=1"
set "OLLAMA_KV_CACHE_TYPE=q8_0"
set "OLLAMA_NUM_PARALLEL=1"
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
  start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
) else (
  start "" /min ollama serve
)
echo.
echo Done. Ollama is running with the cooler settings. Restart Archie too.
pause
