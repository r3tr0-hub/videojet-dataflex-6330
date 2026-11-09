@echo off
setlocal
cd /d "%~dp0"
start "" /wait "%~dp0Videojet6330.Diagnostics.exe" --selftest "%~dp0selftest_result.txt"
if exist "%~dp0selftest_result.txt" type "%~dp0selftest_result.txt"
pause
