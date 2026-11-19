@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Legal AI Copilot Workbench

echo.
echo  ============================================
echo   Legal AI Copilot Workbench
echo   Starting... please wait a few seconds
echo  ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python virtual environment not found (.venv).
  echo Please contact the maintainer. Press any key to exit.
  pause >nul
  exit /b 1
)

echo Local access : http://localhost:8501
echo Phone access : use the LAN IP shown below, same WiFi
echo.

rem Start Streamlit; it opens the default browser automatically.
".venv\Scripts\python.exe" -m streamlit run app\streamlit_app.py --server.port 8501 --server.address 0.0.0.0

echo.
echo Server stopped. Press any key to close this window.
pause >nul
