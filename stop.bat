@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 新西方留学服务 - 停止
set PORT=8010
set FOUND=0

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
  wmic process where "ProcessId=%%a" get CommandLine /value 2>nul | findstr /i "uvicorn main:app" >nul
  if !errorlevel!==0 (
    taskkill /PID %%a /F >nul
    echo [已停止] 新西方留学服务后端（PID %%a，端口 %PORT%），页面端已随之关闭。
    set FOUND=1
  ) else (
    echo [警告] 端口 %PORT% 上的进程 PID %%a 不是本系统后端，为安全起见未停止。
    set FOUND=1
  )
)

if %FOUND%==0 echo [提示] 未发现运行中的新西方留学服务后端（端口 %PORT%），无需停止。
pause
exit /b 0
