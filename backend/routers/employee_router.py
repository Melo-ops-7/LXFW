"""员工业务助手路由（FR-016 ~ FR-022）。"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import auth
import schemas
from database import db, rows_to_dicts
from rules import nl2sql

router = APIRouter(prefix="/api/employee", tags=["员工侧"])
_FMT = "%Y-%m-%d %H:%M:%S"
LEAD_STATUSES = {"新增意向", "跟进中", "已签约", "已流失"}


# ---------- FR-016 意向客户录入 ----------
@router.post("/leads", summary="录入意向客户")
def create_lead(body: schemas.LeadIn, user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    owner = body.owner_employee_id or (user["id"] if user["user_type"] == "EMPLOYEE" else 2)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO crm_lead(customer_name,contact_info,background_info,follow_up_history,"
            "status,owner_employee_id) VALUES(?,?,?,?, '新增意向', ?)",
            (body.customer_name, body.contact_info, body.background_info,
             body.follow_up_history or json.dumps([], ensure_ascii=False), owner))
        row = conn.execute("SELECT * FROM crm_lead WHERE id=?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "message": f"客户「{body.customer_name}」已录入，初始状态「新增意向」。"}


# ---------- FR-017 意向客户查询 ----------
@router.get("/leads", summary="查询意向客户列表")
def list_leads(status: str = None, owner_employee_id: int = None, keyword: str = None,
               user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    sql = "SELECT l.*, u.real_name AS owner_name FROM crm_lead l " \
          "LEFT JOIN sys_user u ON u.id=l.owner_employee_id WHERE 1=1"
    params = []
    if status:
        sql += " AND l.status=?"
        params.append(status)
    if owner_employee_id:
        sql += " AND l.owner_employee_id=?"
        params.append(owner_employee_id)
    if keyword:
        sql += " AND (l.customer_name LIKE ? OR l.background_info LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    sql += " ORDER BY l.id DESC"
    with db() as conn:
        rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    for r in rows:
        try:
            r["follow_up_history"] = json.loads(r["follow_up_history"] or "[]")
        except (ValueError, TypeError):
            pass
    return rows


@router.get("/leads/{lead_id}", summary="客户详情")
def lead_detail(lead_id: int, user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM crm_lead WHERE id=?", (lead_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="客户不存在")
    result = dict(row)
    try:
        result["follow_up_history"] = json.loads(result["follow_up_history"] or "[]")
    except (ValueError, TypeError):
        pass
    return result


@router.put("/leads/{lead_id}", summary="更新客户字段")
def update_lead(lead_id: int, body: schemas.LeadUpdateIn,
                user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM crm_lead WHERE id=?", (lead_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="客户不存在")
        fields, params = [], []
        for k in ("contact_info", "background_info", "follow_up_history"):
            v = getattr(body, k)
            if v is not None:
                fields.append(f"{k}=?")
                params.append(v)
        if fields:
            fields.append("update_time=?")
            params.append(datetime.now().strftime(_FMT))
            params.append(lead_id)
            conn.execute(f"UPDATE crm_lead SET {','.join(fields)} WHERE id=?", params)
        updated = conn.execute("SELECT * FROM crm_lead WHERE id=?", (lead_id,)).fetchone()
    return dict(updated)


# ---------- FR-018 客户状态流转 ----------
@router.post("/leads/{lead_id}/status", summary="客户状态流转")
def lead_status(lead_id: int, body: schemas.LeadStatusIn,
                user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    if body.status not in LEAD_STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"非法状态「{body.status}」，仅允许：新增意向/跟进中/已签约/已流失")
    with db() as conn:
        row = conn.execute("SELECT * FROM crm_lead WHERE id=?", (lead_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="客户不存在")
        conn.execute("UPDATE crm_lead SET status=?, update_time=? WHERE id=?",
                     (body.status, datetime.now().strftime(_FMT), lead_id))
    return {"id": lead_id, "status": body.status,
            "message": f"客户「{row['customer_name']}」状态已更新为「{body.status}」。"}


# ---------- FR-019 员工日报 ----------
@router.post("/reports", summary="写入日报")
def create_report(body: schemas.ReportIn, user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    employee_id = body.employee_id or (user["id"] if user["user_type"] == "EMPLOYEE" else None)
    if not employee_id:
        raise HTTPException(status_code=400, detail="缺少员工ID")
    report_date = body.report_date or datetime.now().strftime("%Y-%m-%d")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO employee_daily_report(employee_id,report_date,content) VALUES(?,?,?)",
            (employee_id, report_date, body.content))
        row = conn.execute("SELECT * FROM employee_daily_report WHERE id=?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "message": "日报已记录。"}


@router.get("/reports", summary="查询日报")
def list_reports(employee_id: int = None, report_date: str = None,
                 user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    sql = "SELECT r.*, u.real_name AS employee_name FROM employee_daily_report r " \
          "LEFT JOIN sys_user u ON u.id=r.employee_id WHERE 1=1"
    params = []
    if employee_id:
        sql += " AND r.employee_id=?"
        params.append(employee_id)
    if report_date:
        sql += " AND r.report_date=?"
        params.append(report_date)
    sql += " ORDER BY r.report_date DESC, r.id DESC LIMIT 100"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


# ---------- FR-020/021 成绩录入与查询 ----------
@router.post("/scores", summary="录入学生成绩")
def create_score(body: schemas.ScoreIn, user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    with db() as conn:
        stu = conn.execute("SELECT id FROM sys_user WHERE id=? AND user_type='STUDENT'",
                           (body.student_id,)).fetchone()
        if not stu:
            raise HTTPException(status_code=404, detail="学生不存在")
        cur = conn.execute(
            "INSERT INTO student_score(student_id,course_name,score,semester) VALUES(?,?,?,?)",
            (body.student_id, body.course_name, body.score, body.semester))
        row = conn.execute("SELECT * FROM student_score WHERE id=?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "message": "成绩已录入。"}


@router.get("/scores", summary="查询成绩")
def list_scores(student_id: int = None, course_name: str = None,
                user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    sql = "SELECT s.*, u.real_name AS student_name FROM student_score s " \
          "LEFT JOIN sys_user u ON u.id=s.student_id WHERE 1=1"
    params = []
    if student_id:
        sql += " AND s.student_id=?"
        params.append(student_id)
    if course_name:
        sql += " AND s.course_name LIKE ?"
        params.append(f"%{course_name}%")
    sql += " ORDER BY s.id DESC"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


# ---------- 学生名单（供录入成绩选择） ----------
@router.get("/students", summary="学生名单")
def list_students(user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    with db() as conn:
        return rows_to_dicts(conn.execute(
            "SELECT id,real_name,department,contact_info FROM sys_user "
            "WHERE user_type='STUDENT' AND status='正常' ORDER BY id").fetchall())


# ---------- FR-022 NL2SQL ----------
@router.post("/nl2sql", summary="自然语言指令处理")
def nl2sql_cmd(body: schemas.NL2SQLIn, user=Depends(auth.require_roles("顾问", "班主任", "管理员"))):
    employee_id = body.employee_id or (user["id"] if user["user_type"] == "EMPLOYEE" else None)
    return nl2sql.process(body.text, employee_id)