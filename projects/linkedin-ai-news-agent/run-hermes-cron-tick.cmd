@echo off
set "PATH=C:\OBSIDIAN\.hermes-runtime\bin;%PATH%"
set "HERMES_HOME=C:\Users\STPG PCAU07\.hermes"
set "PYTHONIOENCODING=utf-8"
cd /d C:\OBSIDIAN
"C:\OBSIDIAN\.hermes-runtime\bin\hermes.exe" cron tick --accept-hooks
