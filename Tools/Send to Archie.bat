@echo off
REM Windows right-click -> Send to -> Archie: hands the files to Archie, which shows a card for each.
chcp 65001 >nul
for %%I in ("%~dp0..") do set "ARCHIE=%%~fI\"
:next
if "%~1"=="" goto :eof
for %%F in ("%~1") do >>"%ARCHIE%inbox_queue.txt" echo(%%~fF
shift
goto next
