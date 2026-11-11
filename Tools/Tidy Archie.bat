@echo off
title Tidying the Archie folder
cd /d "%~dp0"
echo Tidying D:\Archie. Nothing is deleted: everything is moved into folders.
echo.
if not exist "Tools\Get Models.bat" (echo The new Tools folder is missing. Nothing was moved. & pause & exit /b 1)
mkdir Backups 2>nul
mkdir "Backups\old helper bats" 2>nul
mkdir Guides 2>nul
mkdir "Old Downloads" 2>nul
echo Backups (.bak- files) into Backups ...
for %%F in (*.bak-*) do move /y "%%F" "Backups\" >nul
echo Helper .bat files: the copies in Tools take over, the old ones go to Backups\old helper bats ...
if exist "Tools\Get Code Editor.bat" if exist "Get Code Editor.bat" move /y "Get Code Editor.bat" "Backups\old helper bats\" >nul
if exist "Tools\Get Handwriting Model.bat" if exist "Get Handwriting Model.bat" move /y "Get Handwriting Model.bat" "Backups\old helper bats\" >nul
if exist "Tools\Get Image Maker.bat" if exist "Get Image Maker.bat" move /y "Get Image Maker.bat" "Backups\old helper bats\" >nul
if exist "Tools\Get Models.bat" if exist "Get Models.bat" move /y "Get Models.bat" "Backups\old helper bats\" >nul
if exist "Tools\Get Sketch Model.bat" if exist "Get Sketch Model.bat" move /y "Get Sketch Model.bat" "Backups\old helper bats\" >nul
if exist "Tools\Get Voice.bat" if exist "Get Voice.bat" move /y "Get Voice.bat" "Backups\old helper bats\" >nul
if exist "Tools\Get Wikipedia.bat" if exist "Get Wikipedia.bat" move /y "Get Wikipedia.bat" "Backups\old helper bats\" >nul
if exist "Tools\Install Extras.bat" if exist "Install Extras.bat" move /y "Install Extras.bat" "Backups\old helper bats\" >nul
if exist "Tools\Install LocalSend.bat" if exist "Install LocalSend.bat" move /y "Install LocalSend.bat" "Backups\old helper bats\" >nul
if exist "Tools\Fix Brief.bat" if exist "Fix Brief.bat" move /y "Fix Brief.bat" "Backups\old helper bats\" >nul
if exist "Tools\Fix Image Maker.bat" if exist "Fix Image Maker.bat" move /y "Fix Image Maker.bat" "Backups\old helper bats\" >nul
if exist "Tools\Test Image Maker.bat" if exist "Test Image Maker.bat" move /y "Test Image Maker.bat" "Backups\old helper bats\" >nul
if exist "Tools\Create Shortcut.bat" if exist "Create Shortcut.bat" move /y "Create Shortcut.bat" "Backups\old helper bats\" >nul
if exist "Tools\Setup Archie.bat" if exist "Setup Archie.bat" move /y "Setup Archie.bat" "Backups\old helper bats\" >nul
if exist "Tools\Vault Check.bat" if exist "Vault Check.bat" move /y "Vault Check.bat" "Backups\old helper bats\" >nul
if exist "Tools\Update Archie Coach.bat" if exist "Update Archie Coach.bat" move /y "Update Archie Coach.bat" "Backups\old helper bats\" >nul
echo Guides ...
if exist "README.md" move /y "README.md" "Guides\" >nul
if exist "Archie Obsidian Guide.html" move /y "Archie Obsidian Guide.html" "Guides\" >nul
if exist "Archie+Obsidian Guide.html" move /y "Archie+Obsidian Guide.html" "Backups\" >nul
echo Old downloads ...
for %%F in (libzim-*.whl "World-matched-by-others.zip") do if exist "%%~F" move /y "%%~F" "Old Downloads\" >nul
echo.
echo Done. Top of the folder now: Start / Restart / Update Archie, Set up phone, Allow Archie Lite,
echo the Manual, Archie's code and data, and the folders Tools, Guides, Backups, Old Downloads.
echo This tidy-up file moves itself into Tools now.
echo.
pause
(goto) 2>nul & move /y "%~f0" "%~dp0Tools\" >nul
