@echo off
chcp 65001 >nul
title 放行手机访问 - 律师工作台

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo   [需要管理员权限]
  echo   请关闭本窗口，右键点击本文件，选择「以管理员身份运行」。
  echo.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   律师工作台 - 放行同一 WiFi 下的手机访问
echo ============================================================
echo.
echo   作用：在 Windows 防火墙中放行 TCP 8501 端口，
echo         仅允许「本地子网」(同一 WiFi/局域网) 访问，
echo         不对外网开放，避免安全风险。
echo.

echo   正在添加防火墙规则...
netsh advfirewall firewall add rule name="Legal Workbench Streamlit 8501 (LAN only)" dir=in action=allow protocol=TCP localport=8501 remoteip=localsubnet profile=private,public

echo.
echo   完成。现在手机连上和电脑相同的 WiFi 后，
echo   用浏览器打开电脑上显示的 Network URL（形如 http://10.x.x.x:8501）即可。
echo.
echo   如需撤销此规则（恢复默认阻止），请以管理员身份运行同目录的
echo   「撤销手机访问放行(右键管理员运行).bat」。
echo.
pause
