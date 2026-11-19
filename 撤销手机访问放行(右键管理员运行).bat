@echo off
chcp 65001 >nul
title 撤销手机访问放行 - 律师工作台

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
echo   正在撤销 8501 端口的防火墙放行规则...
netsh advfirewall firewall delete rule name="Legal Workbench Streamlit 8501 (LAN only)"

echo.
echo   完成。手机现已无法通过网络访问工作台。
echo.
pause
