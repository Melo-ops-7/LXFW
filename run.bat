@echo off
chcp 65001 >nul
setlocal
title 新西方留学服务 - 启动
set PORT=8010
cd /d "%~dp0backend"

netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul
if %errorlevel%==0 goto already

echo 正在启动新西方留学服务智能助手系统（端口 %PORT%）...
start "XinXiFang-Backend" /MIN python -X utf8 -m uvicorn main:app --host 0.0.0.0 --port %PORT%
ping -n 6 127.0.0.1 >nul
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul
if %errorlevel%==0 goto ok

echo [失败] 后端未能启动，请确认已安装 Python 依赖（pip install -r requirements.txt）。
pause
exit /b 1

:ok
echo.
echo ============================================
echo  启动成功！
echo  官网首页   http://localhost:%PORT%/
echo  学生端     http://localhost:%PORT%/student.html
echo  员工后台   http://localhost:%PORT%/staff.html
echo  停止服务   双击 stop.bat
echo ============================================
pause
exit /b 0

:already
echo [提示] 端口 %PORT% 已有服务在运行，无需重复启动。
echo 访问: http://localhost:%PORT%/
pause
exit /b 0
