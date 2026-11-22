@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py server.py
) else (
  python server.py
)
if errorlevel 1 echo 启动失败，请先执行 install_windows.bat，并阅读 README.md
pause
