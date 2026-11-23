"""演示级认证与权限控制（需求 12.2）。

- 前端用户：POST /api/auth/login 换取令牌（Authorization: Bearer <token>）
- 令牌持久化到 SQLite sys_token 表：后端重启不掉线，同一账号多端并行登录互不影响
- Dify 工具调用：请求头 X-API-Key 携带 TOOL_API_KEY，可访问全部业务接口
- 角色：STUDENT（学生）；EMPLOYEE + employee_role（顾问/班主任/管理员）
"""
import json
import secrets
import time

from fastapi import Header, HTTPException, Request

import config
from database import db, rows_to_dicts
from seed import verify_password


def login(username: str, password: str) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM sys_user WHERE username=?", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        user = dict(row)
        if user["status"] != "正常":
            raise HTTPException(status_code=403, detail="账号已被禁用")
        user.pop("password_hash")
        token = secrets.token_hex(24)
        conn.execute("DELETE FROM sys_token WHERE expire < ?", (time.time(),))  # 顺带清理过期令牌
        conn.execute(
            "INSERT INTO sys_token(token, user_json, expire) VALUES(?,?,?)",
            (token, json.dumps(user, ensure_ascii=False), time.time() + config.TOKEN_TTL),
        )
    return {"token": token, "user": user}


def _user_from_request(request: Request, authorization: str, x_api_key: str):
    """解析请求身份：API Key（Dify）优先，其次 Bearer 令牌。"""
    if x_api_key:
        if x_api_key != config.TOOL_API_KEY:
            raise HTTPException(status_code=401, detail="API Key 无效")
        return {"id": 0, "real_name": "Dify工具", "user_type": "TOOL", "employee_role": None}
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        with db() as conn:
            row = conn.execute("SELECT user_json, expire FROM sys_token WHERE token=?", (token,)).fetchone()
        if row and row["expire"] >= time.time():
            return json.loads(row["user_json"])
        if row:  # 令牌过期：清除后要求重新登录
            with db() as conn:
                conn.execute("DELETE FROM sys_token WHERE token=?", (token,))
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return None


def current_user(request: Request,
                 authorization: str = Header(default=""),
                 x_api_key: str = Header(default="")):
    """必须登录（学生/员工/工具）。"""
    user = _user_from_request(request, authorization, x_api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    return user


def optional_user(request: Request,
                  authorization: str = Header(default=""),
                  x_api_key: str = Header(default="")):
    """可匿名（官网客服/报名）。"""
    return _user_from_request(request, authorization, x_api_key)


def require_roles(*roles):
    """角色守卫工厂：roles 为允许的员工角色；'STUDENT' 表示学生；'TOOL' 始终放行。"""
    def guard(request: Request,
              authorization: str = Header(default=""),
              x_api_key: str = Header(default="")):
        user = _user_from_request(request, authorization, x_api_key)
        if user is None:
            raise HTTPException(status_code=401, detail="未登录")
        if user["user_type"] == "TOOL":
            return user
        if user["user_type"] == "STUDENT" and "STUDENT" in roles:
            return user
        if user["user_type"] == "EMPLOYEE" and user.get("employee_role") in roles:
            return user
        raise HTTPException(status_code=403, detail="当前角色无权执行该操作")
    return guard


def get_user(user_id: int):
    with db() as conn:
        row = conn.execute("SELECT id,real_name,user_type,employee_role,department FROM sys_user WHERE id=?",
                           (user_id,)).fetchone()
    return dict(row) if row else None


def find_homeroom_teachers():
    """查找班主任（用于高危预警通知）。"""
    with db() as conn:
        rows = conn.execute(
            "SELECT id,real_name,contact_info FROM sys_user "
            "WHERE user_type='EMPLOYEE' AND employee_role='班主任' AND status='正常'").fetchall()
    return rows_to_dicts(rows)