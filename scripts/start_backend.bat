@echo off
chcp 65001 >nul
title 新西方留学服务智能助手系统 - 后端服务 (8010)
cd /d "%~dp0..\backend"
echo ============================================
echo  新西方留学服务智能教育服务助手系统
echo  官网首页:   http://localhost:8010/
echo  学生端:     http://localhost:8010/student.html
echo  员工后台:   http://localhost:8010/staff.html
echo  API文档:    http://localhost:8010/docs
echo ============================================
python -X utf8 -m uvicorn main:app --host 0.0.0.0 --port 8010
pause