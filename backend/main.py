"""新西方留学服务智能教育服务助手系统 - FastAPI 入口。

启动：uvicorn main:app --host 0.0.0.0 --port 8010
- /            官网首页（客户侧）
- /student.html 学生端
- /staff.html   员工与后台（顾问/班主任/管理员）
- /docs         Swagger 接口文档
- /openapi.json Dify 自定义工具导入源
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from database import init_db
from routers import (admin_router, auth_router, chat_router, employee_router,
                     profile_router, service_router, student_router)

app = FastAPI(
    title="新西方留学服务智能教育服务助手系统 API",
    description="Dify 编排层（大脑）+ FastAPI 业务后端（手脚）+ SQLite 数据层。"
                "Dify 自定义工具调用需携带请求头 X-API-Key。",
    version="1.0.0",
)

# 跨域（演示级；生产应收敛来源）
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], allow_credentials=False,
)

app.include_router(auth_router.router)
app.include_router(profile_router.router)
app.include_router(student_router.router)
app.include_router(employee_router.router)
app.include_router(service_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router.router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health", tags=["系统公共"], summary="健康检查")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """隐藏内部错误，返回用户可理解提示（需求 11.3）。"""
    return JSONResponse(status_code=500, content={"detail": "系统繁忙，请稍后重试或联系人工客服。"})


# 前端静态资源（三大板块）
frontend_dir = config.PROJECT_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")