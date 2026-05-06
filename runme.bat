@echo off
chcp 65001 >nul
cd /d "%~dp0"
python web2telegraph.py %*
pause
