"""管理后台路由（FR-031 数据展示 + 用户管理 + 系统监控）。"""
from fastapi import APIRouter, Depends, HTTPException

import auth
import schemas
from database import db, rows_to_dicts
from seed import hash_password

router = APIRouter(prefix="/api/admin", tags=["管理后台"])
_admin = auth.require_roles("管理员")


@router.get("/overview", summary="后台数据总览")
def overview(user=Depends(_admin)):
    with db() as conn:
        def count(sql, params=()):
            return conn.execute(sql, params).fetchone()[0]
        lead_status = rows_to_dicts(conn.execute(
            "SELECT status, COUNT(*) AS n FROM crm_lead GROUP BY status").fetchall())
        return {
            "students": count("SELECT COUNT(*) FROM sys_user WHERE user_type='STUDENT'"),
            "employees": count("SELECT COUNT(*) FROM sys_user WHERE user_type='EMPLOYEE'"),
            "leads_total": count("SELECT COUNT(*) FROM crm_lead"),
            "leads_by_status": lead_status,
            "pending_leaves": count("SELECT COUNT(*) FROM student_admin_service WHERE status='待审批'"),
            "open_alerts": count("SELECT COUNT(*) FROM student_psych_alert WHERE status!='已解除'"),
            "high_alerts": count("SELECT COUNT(*) FROM student_psych_alert WHERE risk_level='高' AND status='未处理'"),
            "pending_tickets": count("SELECT COUNT(*) FROM student_feedback_ticket WHERE status!='已解决'"),
            "scores_total": count("SELECT COUNT(*) FROM student_score"),
            "reports_today": count("SELECT COUNT(*) FROM employee_daily_report WHERE report_date=date('now','localtime')"),
            "events": count("SELECT COUNT(*) FROM event_lecture"),
            "registrations": count("SELECT COUNT(*) FROM event_registration"),
            "conversations": count("SELECT COUNT(*) FROM conversation_log"),
        }


@router.get("/users", summary="用户列表")
def list_users(user_type: str = None, user=Depends(_admin)):
    sql = "SELECT id,username,real_name,user_type,employee_role,department,contact_info,status,create_time FROM sys_user"
    params = []
    if user_type:
        sql += " WHERE user_type=?"
        params.append(user_type)
    sql += " ORDER BY id"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


@router.post("/users", summary="新增用户")
def create_user(body: schemas.UserIn, user=Depends(_admin)):
    if body.user_type == "EMPLOYEE" and body.employee_role not in ("顾问", "班主任", "管理员"):
        raise HTTPException(status_code=400, detail="员工角色必须为：顾问/班主任/管理员")
    with db() as conn:
        dup = conn.execute("SELECT id FROM sys_user WHERE username=?", (body.username,)).fetchone()
        if dup:
            raise HTTPException(status_code=400, detail="用户名已存在")
        cur = conn.execute(
            "INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,department,contact_info) "
            "VALUES(?,?,?,?,?,?,?)",
            (body.username, hash_password(body.password), body.real_name, body.user_type,
             body.employee_role, body.department, body.contact_info))
        row = conn.execute(
            "SELECT id,username,real_name,user_type,employee_role,department,status FROM sys_user WHERE id=?",
            (cur.lastrowid,)).fetchone()
    return dict(row)


@router.post("/users/{user_id}/status", summary="启用/禁用用户")
def user_status(user_id: int, body: schemas.UserStatusIn, user=Depends(_admin)):
    with db() as conn:
        row = conn.execute("SELECT id FROM sys_user WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        conn.execute("UPDATE sys_user SET status=?, update_time=datetime('now','localtime') WHERE id=?",
                     (body.status, user_id))
    return {"id": user_id, "status": body.status}


@router.get("/system", summary="系统健康与集成状态")
def system_status(user=Depends(_admin)):
    import config
    return {
        "backend": "ok",
        "database": "ok",
        "dify_agents": {k: ("已配置" if v else "未配置（降级本地应答）")
                        for k, v in config.DIFY_API_KEYS.items()},
        "tool_api_key": "已配置",
    }


@router.get("/conversations", summary="对话记录（心理画像原料）")
def conversations(agent_type: str = None, limit: int = 100, user=Depends(_admin)):
    sql = "SELECT * FROM conversation_log WHERE 1=1"
    params = []
    if agent_type:
        sql += " AND agent_type=?"
        params.append(agent_type)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())