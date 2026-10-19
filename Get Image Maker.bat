@echo off
title Archie - image maker (Stable Diffusion XL, offline)
cd /d "%~dp0"
set "HF_HUB_DISABLE_SYMLINKS_WARNING=1"
set "HF_HUB_VERBOSITY=error"
set "HF_HUB_DISABLE_TELEMETRY=1"
echo ============================================
echo   Archie image maker - runs on YOUR graphics card, no internet after this.
echo   Downloads: PyTorch with CUDA (about 2.5 GB, installs on C:)
echo              the SDXL image model (about 7.3 GB, into D:\Archie\Images)
echo   Needs the internet once. QUIT ARCHIE FIRST (right-click the owl, Quit).
echo ============================================
echo.
set "PY="
if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Could not find Python.
  pause
  exit /b
)
echo [1/3] PyTorch for NVIDIA graphics cards (the big one)...
"%PY%" -m pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu121
echo.
echo [2/3] The image libraries...
"%PY%" -m pip install --upgrade diffusers transformers accelerate safetensors huggingface_hub "numpy<2"
echo.
echo [3/3] The image model...
"%PY%" "%~dp0archie_imagine.py" --download
echo.
echo Done! Start Archie and type something like:
echo     draw a ruined desert city at dusk, concept art
echo The first picture takes a bit longer while the model loads.
pause
