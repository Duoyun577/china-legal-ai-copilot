@echo off
chcp 65001 >nul
title 律师工作台 - 公网访问

cd /d "%~dp0"

set "CLOUDFLARED=%~dp0tools\cloudflared.exe"
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%CLOUDFLARED%" (
  echo.
  echo   [缺少 cloudflared.exe]
  echo   公网组件尚未下载完成，请稍后再试。
  echo.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   律师工作台 - 公网访问（Cloudflare 隧道）
echo ============================================================
echo.
echo   本脚本会做两件事：
echo    1. 确保本机工作台正在运行（端口 8501）
echo    2. 建立一条 Cloudflare 加密隧道，生成公网网址
echo.

REM --- 1. 检查工作台是否已运行，未运行则启动 ---
netstat -ano | findstr ":8501" >nul 2>&1
if %errorlevel% neq 0 (
  echo   工作台未运行，正在启动本机服务...
  start "LegalWorkbench" cmd /c ""%PY%" -m streamlit run app\streamlit_app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true"
  timeout /t 8 /nobreak >nul
) else (
  echo   工作台已在运行。
)

REM --- 2. 启动 Cloudflare 隧道 ---
echo.
echo   正在建立公网隧道，请稍候...
echo.
echo   ★★★ 请在下方输出中找到类似这样的网址并复制： ★★★
echo       https://xxxx-xxxx-xxxx.trycloudflare.com
echo.
echo   这个网址也会自动保存到项目目录的『当前公网地址.txt』，随时可查。
echo   网址每次启动会变化——如需固定网址，需配置 Cloudflare 命名隧道（见公网发布预案.md）。
echo.
echo   关闭本窗口即可停止公网访问。
echo   ============================================================
echo.

REM --protocol http2 is REQUIRED in mainland China (UDP/QUIC is blocked).
REM run_tunnel.py wraps cloudflared and saves the URL to 当前公网地址.txt.
"%PY%" "tools\run_tunnel.py"

pause
