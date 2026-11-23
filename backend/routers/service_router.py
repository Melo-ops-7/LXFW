"""客服与活动路由（FR-023 ~ FR-028，客户侧可匿名访问）。"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import auth
import schemas
from database import db, rows_to_dicts
from rules import profile as profile_rules

router = APIRouter(prefix="/api", tags=["客服与活动"])
_FMT = "%Y-%m-%d %H:%M:%S"


# ---------- FR-023 课程/项目查询 ----------
@router.get("/courses", summary="课程/项目列表")
def list_courses(keyword: str = None, category: str = None):
    sql = "SELECT * FROM course_project WHERE 1=1"
    params = []
    if keyword:
        sql += " AND (project_name LIKE ? OR description LIKE ? OR target_audience LIKE ?)"
        params += [f"%{keyword}%"] * 3
    if category:
        sql += " AND category=?"
        params.append(category)
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


@router.get("/courses/{course_id}", summary="课程/项目详情")
def course_detail(course_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM course_project WHERE id=?", (course_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="项目不存在")
    return dict(row)


# ---------- FR-024 课程推荐（画像研判 + 知识库关键信息） ----------
@router.post("/courses/recommend", summary="课程推荐（先画像研判，再附项目关键信息）")
def recommend(body: schemas.ProfileIn):
    structured = {k: getattr(body, k) for k in
                  ("name", "age", "education", "intent", "language", "hands_on", "budget")}
    result = profile_rules.analyze(body.raw_text, body.llm_profile, structured)
    if result["matches"]:
        with db() as conn:
            names = [m["project"] for m in result["matches"]]
            placeholders = ",".join("?" * len(names))
            rows = rows_to_dicts(conn.execute(
                f"SELECT project_name,category,description,target_audience FROM course_project "
                f"WHERE project_name IN ({placeholders})", names).fetchall())
        info = {r["project_name"]: r for r in rows}
        for m in result["matches"]:
            m["detail"] = info.get(m["project"])
        result["lead_guide"] = "如需进一步了解学费明细与报名流程，可留下姓名与联系方式，顾问将为您一对一解答。"
    return result


# ---------- FR-025 活动查询 ----------
@router.get("/events", summary="活动/讲座列表")
def list_events(event_type: str = None):
    sql = "SELECT * FROM event_lecture WHERE 1=1"
    params = []
    if event_type:
        sql += " AND event_type=?"
        params.append(event_type)
    sql += " ORDER BY start_time"
    with db() as conn:
        rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    for r in rows:
        r["remaining"] = max(0, (r["max_participants"] or 0) - (r["current_participants"] or 0))
        r["is_full"] = r["remaining"] == 0
    return rows


@router.get("/events/registrations", summary="报名记录查询")
def list_registrations(event_id: int = None):
    sql = "SELECT r.*, e.event_name, l.customer_name FROM event_registration r " \
          "LEFT JOIN event_lecture e ON e.id=r.event_id " \
          "LEFT JOIN crm_lead l ON l.id=r.customer_id WHERE 1=1"
    params = []
    if event_id:
        sql += " AND r.event_id=?"
        params.append(event_id)
    sql += " ORDER BY r.id DESC"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


@router.get("/events/{event_id}", summary="活动详情")
def event_detail(event_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM event_lecture WHERE id=?", (event_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="活动不存在")
    result = dict(row)
    result["remaining"] = max(0, (result["max_participants"] or 0) - (result["current_participants"] or 0))
    return result


# ---------- FR-026 活动报名 ----------
@router.post("/events/register", summary="活动报名（名额校验+自动累加）")
def register(body: schemas.RegisterIn, user=Depends(auth.optional_user)):
    with db() as conn:
        # 定位活动：优先 ID，其次名称模糊匹配
        event = None
        if body.event_id:
            event = conn.execute("SELECT * FROM event_lecture WHERE id=?", (body.event_id,)).fetchone()
        elif body.event_name:
            event = conn.execute("SELECT * FROM event_lecture WHERE event_name LIKE ?",
                                 (f"%{body.event_name}%",)).fetchone()
            if not event:
                # 去掉「报名/我要/参加」等口语前缀后再试核心词
                core = body.event_name.replace("报名", "").replace("我要", "").replace("参加", "").strip()
                for row in conn.execute("SELECT * FROM event_lecture").fetchall():
                    if core and (core in row["event_name"] or row["event_name"] in core):
                        event = row
                        break
        if not event:
            raise HTTPException(status_code=404, detail="活动不存在，请确认活动名称")
        event = dict(event)
        if (event["current_participants"] or 0) >= (event["max_participants"] or 0):
            raise HTTPException(status_code=400, detail=f"活动「{event['event_name']}」名额已满，无法报名")

        # 定位/创建客户（访客留资自动沉淀为 CRM 线索）
        customer_id = body.customer_id
        if not customer_id and user and user["user_type"] == "STUDENT":
            customer_id = None  # 学生报名也走留资线索
        if not customer_id:
            name = body.customer_name or (user["real_name"] if user else None) or "匿名访客"
            existing = conn.execute("SELECT id FROM crm_lead WHERE customer_name=? AND contact_info IS ?",
                                    (name, body.contact_info)).fetchone()
            if existing:
                customer_id = existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO crm_lead(customer_name,contact_info,background_info,follow_up_history,"
                    "status,owner_employee_id) VALUES(?,?,?,?, '新增意向', 2)",
                    (name, body.contact_info, f"活动报名自动留资：{event['event_name']}",
                     json.dumps([], ensure_ascii=False)))
                customer_id = cur.lastrowid

        # 防重复报名
        dup = conn.execute("SELECT id FROM event_registration WHERE event_id=? AND customer_id=?",
                           (event["id"], customer_id)).fetchone()
        if dup:
            return {"registration_id": dup["id"], "event_name": event["event_name"],
                    "message": f"您已报名过「{event['event_name']}」，请勿重复报名。"}

        cur = conn.execute(
            "INSERT INTO event_registration(event_id,customer_id,status) VALUES(?,?,'已报名')",
            (event["id"], customer_id))
        conn.execute("UPDATE event_lecture SET current_participants=current_participants+1 WHERE id=?",
                     (event["id"],))
        updated = conn.execute("SELECT * FROM event_lecture WHERE id=?", (event["id"],)).fetchone()
    return {"registration_id": cur.lastrowid, "event_id": event["id"],
            "event_name": event["event_name"], "customer_id": customer_id,
            "current_participants": updated["current_participants"],
            "message": f"报名成功！您已预约「{event['event_name']}」，时间：{event['start_time']}，地点：{event['location']}。"}


# ---------- 官网 FAQ（知识库同源） ----------
@router.get("/faq", summary="常见问题列表")
def faq_list():
    import dify_client
    return dify_client._load_faq()


# ---------- 官网留资 ----------
@router.post("/leads/public", summary="官网访客留资")
def public_lead(body: schemas.LeadIn):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO crm_lead(customer_name,contact_info,background_info,follow_up_history,"
            "status,owner_employee_id) VALUES(?,?,?,?, '新增意向', 2)",
            (body.customer_name, body.contact_info, body.background_info or "官网表单留资",
             json.dumps([], ensure_ascii=False)))
    return {"id": cur.lastrowid, "message": "提交成功，顾问将尽快与您联系。"}