"""留学生智能管家路由（FR-006 ~ FR-015）。"""
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

import auth
import config
import schemas
from database import db, rows_to_dicts
from rules import emotion as emotion_rules
from rules import leave_parser

router = APIRouter(prefix="/api/student", tags=["学生侧"])
_FMT = "%Y-%m-%d %H:%M:%S"


def _check_student(user, student_id):
    """学生只能访问本人数据；员工/工具可访问全部。"""
    if user["user_type"] == "STUDENT" and user["id"] != student_id:
        raise HTTPException(status_code=403, detail="只能访问本人数据")


# ---------- FR-006 请假申请 ----------
@router.post("/leave", summary="提交请假申请")
def create_leave(body: schemas.LeaveIn, user=Depends(auth.require_roles("STUDENT", "班主任", "管理员", "顾问"))):
    _check_student(user, body.student_id)
    start, end = body.start_time, body.end_time
    parsed = True
    if not start or not end:
        start, end, parsed = leave_parser.parse_leave_time(body.reason)
    with db() as conn:
        # 防重复：同一学生相同起止时间+事由的待审批申请直接返回已有记录
        dup = conn.execute(
            "SELECT * FROM student_admin_service WHERE student_id=? AND service_type=? "
            "AND start_time=? AND end_time=? AND reason=? AND status='待审批'",
            (body.student_id, body.service_type, start, end, body.reason)).fetchone()
        if dup:
            return {**dict(dup), "time_parsed": parsed,
                    "message": "已存在相同的待审批请假申请，无需重复提交，请耐心等待班主任审批。"}
        cur = conn.execute(
            "INSERT INTO student_admin_service(student_id,service_type,start_time,end_time,reason,status) "
            "VALUES(?,?,?,?,?,'待审批')",
            (body.student_id, body.service_type, start, end, body.reason))
        row = conn.execute("SELECT * FROM student_admin_service WHERE id=?", (cur.lastrowid,)).fetchone()
    result = dict(row)
    result["time_parsed"] = parsed
    result["message"] = ("请假申请已提交，状态「待审批」，等待班主任审批。" if parsed
                         else "未能从事由中解析出明确时间，已按默认（今天09:00-18:00）提交，状态「待审批」。")
    return result


# ---------- FR-007 请假查询 ----------
@router.get("/leaves", summary="查询请假记录")
def list_leaves(student_id: int = None, status: str = None,
                user=Depends(auth.require_roles("STUDENT", "班主任", "管理员", "顾问"))):
    if user["user_type"] == "STUDENT":
        student_id = user["id"]
    sql = "SELECT s.*, u.real_name AS student_name FROM student_admin_service s " \
          "LEFT JOIN sys_user u ON u.id=s.student_id WHERE 1=1"
    params = []
    if student_id:
        sql += " AND s.student_id=?"
        params.append(student_id)
    if status:
        sql += " AND s.status=?"
        params.append(status)
    sql += " ORDER BY s.id DESC"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


# ---------- FR-008 请假审批 ----------
@router.post("/leave/approve", summary="审批请假（班主任/管理员）")
def approve_leave(body: schemas.LeaveApproveIn, user=Depends(auth.require_roles("班主任", "管理员"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM student_admin_service WHERE id=?", (body.leave_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="请假申请不存在")
        new_status = "已通过" if body.approved else "已驳回"
        approver = body.approver_id or (user["id"] if user["user_type"] == "EMPLOYEE" else None)
        conn.execute("UPDATE student_admin_service SET status=?, approver_id=?, update_time=? WHERE id=?",
                     (new_status, approver, datetime.now().strftime(_FMT), body.leave_id))
        updated = conn.execute("SELECT * FROM student_admin_service WHERE id=?", (body.leave_id,)).fetchone()
    return {"id": body.leave_id, "status": new_status, "record": dict(updated),
            "message": f"审批完成：{new_status}。"}


# ---------- FR-009/010/011 情绪评估 + 画像 + 预警 ----------
@router.post("/emotion", summary="情绪评估（含心理画像累积与高危预警）")
def assess_emotion(body: schemas.EmotionIn, user=Depends(auth.require_roles("STUDENT", "班主任", "管理员"))):
    _check_student(user, body.student_id)
    ev = emotion_rules.evaluate(body.text, body.emotion_tag, body.emotion_score)
    now = datetime.now().strftime(_FMT)
    alert_id, notified = None, []

    with db() as conn:
        # 心理画像 upsert（FR-010）
        row = conn.execute("SELECT * FROM student_psych_profile WHERE student_id=?",
                           (body.student_id,)).fetchone()
        history = []
        if row:
            try:
                history = json.loads(row["emotion_history"] or "[]")
            except (ValueError, TypeError):
                history = []
        history.append({"time": now, "tag": ev["emotion_tag"], "score": ev["emotion_score"]})
        history = history[-config.EMOTION_HISTORY_LIMIT:]
        conn.execute(
            "INSERT INTO student_psych_profile(student_id,latest_emotion_tag,emotion_score,"
            "last_interaction_time,emotion_history,update_time) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(student_id) DO UPDATE SET latest_emotion_tag=excluded.latest_emotion_tag, "
            "emotion_score=excluded.emotion_score, last_interaction_time=excluded.last_interaction_time, "
            "emotion_history=excluded.emotion_history, update_time=excluded.update_time",
            (body.student_id, ev["emotion_tag"], ev["emotion_score"], now,
             json.dumps(history, ensure_ascii=False), now))

        # 高危预警（FR-011）：写预警表 + 通知班主任
        if ev["alerted"]:
            teachers = auth.find_homeroom_teachers()
            teacher_id = teachers[0]["id"] if teachers else None
            reason = ("命中高危关键词：" + "、".join(ev["hit_keywords"])) if ev["hit_keywords"] \
                else f"LLM评估高危（分值{ev['emotion_score']}）：{body.text[:100]}"
            cur = conn.execute(
                "INSERT INTO student_psych_alert(student_id,trigger_reason,risk_level,status,teacher_id) "
                "VALUES(?,?,?,'未处理',?)", (body.student_id, reason, "高", teacher_id))
            alert_id = cur.lastrowid
            notified = [t["real_name"] for t in teachers]

        # 对话沉淀（FR-029）
        conn.execute(
            "INSERT INTO conversation_log(user_id,agent_type,user_input,ai_reply,emotion_tag) "
            "VALUES(?,?,?,?,?)",
            (str(body.student_id), "student", body.text, None, ev["emotion_tag"]))

    if ev["alerted"]:
        message = "已触发高危预警并通知班主任，请尽快关注该学生。"
        if notified:
            message += f"（已通知：{'、'.join(notified)}）"
    elif ev["emotion_score"] >= config.ALERT_WATCH_THRESHOLD:
        message = "已记录情绪状态（关注级），建议班主任持续关注。"
    else:
        message = "情绪状态已记录。"
    return {"student_id": body.student_id, "emotion_tag": ev["emotion_tag"],
            "emotion_score": ev["emotion_score"], "risk_level": ev["risk_level"],
            "alerted": ev["alerted"], "alert_id": alert_id, "message": message}


@router.get("/psych-profile", summary="查询学生心理画像（仅班主任/管理员可见）")
def psych_profile(student_id: int, user=Depends(auth.require_roles("班主任", "管理员"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM student_psych_profile WHERE student_id=?",
                           (student_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="该学生暂无心理画像")
    result = dict(row)
    try:
        result["emotion_history"] = json.loads(result["emotion_history"] or "[]")
    except (ValueError, TypeError):
        result["emotion_history"] = []
    return result


@router.get("/alerts", summary="查询心理预警列表")
def list_alerts(status: str = None, student_id: int = None,
                user=Depends(auth.require_roles("班主任", "管理员"))):
    sql = "SELECT a.*, u.real_name AS student_name, t.real_name AS teacher_name " \
          "FROM student_psych_alert a LEFT JOIN sys_user u ON u.id=a.student_id " \
          "LEFT JOIN sys_user t ON t.id=a.teacher_id WHERE 1=1"
    params = []
    if status:
        sql += " AND a.status=?"
        params.append(status)
    if student_id:
        sql += " AND a.student_id=?"
        params.append(student_id)
    sql += " ORDER BY a.id DESC"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


@router.post("/alerts/{alert_id}/status", summary="更新预警处理状态")
def update_alert(alert_id: int, body: schemas.AlertStatusIn,
                 user=Depends(auth.require_roles("班主任", "管理员"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM student_psych_alert WHERE id=?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="预警记录不存在")
        teacher = body.teacher_id or (user["id"] if user["user_type"] == "EMPLOYEE" else row["teacher_id"])
        conn.execute("UPDATE student_psych_alert SET status=?, teacher_id=? WHERE id=?",
                     (body.status, teacher, alert_id))
    return {"id": alert_id, "status": body.status, "message": f"预警状态已更新为「{body.status}」。"}


# ---------- 心情打卡（学生每日反馈；连续3天最差心情→关注级，连续5天→高危预警通知班主任） ----------
MOOD_LABELS = {1: "很好", 2: "还不错", 3: "一般", 4: "很低落"}
WORST_MOOD = 4
MOOD_WATCH_DAYS = 3
MOOD_STREAK_ALERT_DAYS = 5


def _mood_streak(conn, student_id: int, today) -> int:
    """截至 today 连续选择最差心情的天数（缺卡即中断）。"""
    rows = conn.execute(
        "SELECT mood_date, mood FROM student_mood WHERE student_id=? AND mood_date<=? "
        "ORDER BY mood_date DESC LIMIT 15", (student_id, today.isoformat())).fetchall()
    by_date = {r["mood_date"]: r["mood"] for r in rows}
    streak, d = 0, today
    while by_date.get(d.isoformat()) == WORST_MOOD:
        streak += 1
        d -= timedelta(days=1)
    return streak


@router.post("/mood", summary="今日心情打卡")
def check_in_mood(body: schemas.MoodIn, user=Depends(auth.require_roles("STUDENT", "班主任", "管理员"))):
    _check_student(user, body.student_id)
    today = date.today()
    now = datetime.now().strftime(_FMT)
    alert_id, notified, risk_level = None, [], None
    with db() as conn:
        conn.execute(
            "INSERT INTO student_mood(student_id,mood_date,mood,create_time) VALUES(?,?,?,?) "
            "ON CONFLICT(student_id,mood_date) DO UPDATE SET mood=excluded.mood, create_time=excluded.create_time",
            (body.student_id, today.isoformat(), body.mood, now))
        streak = _mood_streak(conn, body.student_id, today)
        if streak >= MOOD_WATCH_DAYS:
            risk_level = "高" if streak >= MOOD_STREAK_ALERT_DAYS else "中"
            since = (today - timedelta(days=streak - 1)).isoformat()
            reason = (f"心情打卡：连续{streak}天选择「很低落」（{since} 至 {today.isoformat()}），"
                      + ("请尽快关注该学生心理状态并主动联系。" if risk_level == "高"
                         else "建议班主任持续关注该学生状态。"))
            existing = conn.execute(
                "SELECT * FROM student_psych_alert WHERE student_id=? AND trigger_reason LIKE '心情打卡%' "
                "AND create_time>=? ORDER BY id DESC LIMIT 1",
                (body.student_id, since + " 00:00:00")).fetchone()
            teachers = auth.find_homeroom_teachers()
            teacher_id = teachers[0]["id"] if teachers else None
            if not existing:
                cur = conn.execute(
                    "INSERT INTO student_psych_alert(student_id,trigger_reason,risk_level,status,teacher_id,create_time) "
                    "VALUES(?,?,?,'未处理',?,?)", (body.student_id, reason, risk_level, teacher_id, now))
                alert_id = cur.lastrowid
                notified = [t["real_name"] for t in teachers]
            elif risk_level == "高" and existing["risk_level"] != "高":
                # 关注级升级为高危
                conn.execute("UPDATE student_psych_alert SET risk_level='高', trigger_reason=? WHERE id=?",
                             (reason, existing["id"]))
                alert_id = existing["id"]
                notified = [t["real_name"] for t in teachers]
            else:
                alert_id = existing["id"]
    if risk_level == "高" and notified:
        message = ("已记录你的心情。注意到你最近连续几天情绪低落，班主任会尽快来关心你。"
                   "如需倾诉可随时找老师，或拨打心理援助热线 12356。")
    elif risk_level == "中":
        message = ("已记录今天的心情。最近几天你似乎情绪不高，老师会多留意你。"
                   "愿意的话，可以和智能管家或班主任聊聊。")
    elif body.mood == WORST_MOOD:
        message = "已记录今天的心情。低落的时候别一个人扛着，可以和智能管家聊聊，或找班主任谈谈心。"
    else:
        message = f"已记录今天的心情：{MOOD_LABELS[body.mood]}。愿你保持好状态！"
    return {"student_id": body.student_id, "mood_date": today.isoformat(), "mood": body.mood,
            "mood_label": MOOD_LABELS[body.mood], "streak": streak,
            "risk_level": risk_level, "watch": streak >= MOOD_WATCH_DAYS,
            "alerted": risk_level == "高" and bool(notified), "alert_id": alert_id, "message": message}


@router.get("/mood", summary="查询心情打卡（今日状态+近14天记录）")
def get_mood(student_id: int = None, user=Depends(auth.require_roles("STUDENT", "班主任", "管理员", "顾问"))):
    if user["user_type"] == "STUDENT":
        student_id = user["id"]
    if not student_id:
        raise HTTPException(status_code=400, detail="缺少 student_id")
    _check_student(user, student_id)
    today = date.today()
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            "SELECT mood_date, mood FROM student_mood WHERE student_id=? ORDER BY mood_date DESC LIMIT 14",
            (student_id,)).fetchall())
        streak = _mood_streak(conn, student_id, today)
    today_row = next((r for r in rows if r["mood_date"] == today.isoformat()), None)
    return {"student_id": student_id, "today": today_row["mood"] if today_row else None,
            "streak": streak, "records": rows, "mood_labels": MOOD_LABELS}


# ---------- FR-012/013/014 售后反馈 ----------
@router.post("/feedback", summary="提交售后反馈/投诉")
def create_feedback(body: schemas.FeedbackIn, user=Depends(auth.require_roles("STUDENT", "班主任", "管理员"))):
    _check_student(user, body.student_id)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO student_feedback_ticket(student_id,content,detail,status) VALUES(?,?,?,'待处理')",
            (body.student_id, body.content, body.detail))
        row = conn.execute("SELECT * FROM student_feedback_ticket WHERE id=?", (cur.lastrowid,)).fetchone()
    return {**dict(row), "message": "反馈已提交，工单状态「待处理」，老师跟进解决后会通知您。"}


@router.get("/feedbacks", summary="查询反馈工单")
def list_feedbacks(student_id: int = None, status: str = None,
                   user=Depends(auth.require_roles("STUDENT", "班主任", "管理员", "顾问"))):
    if user["user_type"] == "STUDENT":
        student_id = user["id"]
    sql = "SELECT t.*, u.real_name AS student_name FROM student_feedback_ticket t " \
          "LEFT JOIN sys_user u ON u.id=t.student_id WHERE 1=1"
    params = []
    if student_id:
        sql += " AND t.student_id=?"
        params.append(student_id)
    if status:
        sql += " AND t.status=?"
        params.append(status)
    sql += " ORDER BY t.id DESC"
    with db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


@router.post("/feedback/{ticket_id}/resolve", summary="解决工单并通知学生")
def resolve_feedback(ticket_id: int, body: schemas.FeedbackResolveIn,
                     user=Depends(auth.require_roles("班主任", "管理员"))):
    with db() as conn:
        row = conn.execute("SELECT * FROM student_feedback_ticket WHERE id=?", (ticket_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="工单不存在")
        conn.execute("UPDATE student_feedback_ticket SET status='已解决', solution=?, is_notified=1, "
                     "update_time=? WHERE id=?",
                     (body.solution, datetime.now().strftime(_FMT), ticket_id))
        updated = conn.execute("SELECT * FROM student_feedback_ticket WHERE id=?", (ticket_id,)).fetchone()
    return {"id": ticket_id, "status": "已解决", "is_notified": 1, "record": dict(updated),
            "message": f"工单已解决并已通知学生：您的反馈「{row['content']}」已处理完毕。"}


# ---------- FR-015 成绩查询 ----------
@router.get("/scores", summary="查询学生成绩")
def list_scores(student_id: int = None, course_name: str = None,
                user=Depends(auth.require_roles("STUDENT", "班主任", "管理员", "顾问"))):
    if user["user_type"] == "STUDENT":
        student_id = user["id"]
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


# ---------- 学生自助总览（供 Dify 记录查询分支一次取回） ----------
@router.get("/overview", summary="学生自助总览（请假/成绩/工单/心理画像）")
def overview(student_id: int, user=Depends(auth.require_roles("STUDENT", "班主任", "管理员"))):
    _check_student(user, student_id)
    with db() as conn:
        leaves = rows_to_dicts(conn.execute(
            "SELECT * FROM student_admin_service WHERE student_id=? ORDER BY id DESC LIMIT 10",
            (student_id,)).fetchall())
        scores = rows_to_dicts(conn.execute(
            "SELECT * FROM student_score WHERE student_id=? ORDER BY id DESC LIMIT 20",
            (student_id,)).fetchall())
        tickets = rows_to_dicts(conn.execute(
            "SELECT * FROM student_feedback_ticket WHERE student_id=? ORDER BY id DESC LIMIT 10",
            (student_id,)).fetchall())
        profile = conn.execute("SELECT * FROM student_psych_profile WHERE student_id=?",
                               (student_id,)).fetchone()
    # 心理画像仅班主任/管理员可见，学生本人不展示
    show_psych = user["user_type"] != "STUDENT"
    return {"student_id": student_id, "leaves": leaves, "scores": scores,
            "feedbacks": tickets, "psych_profile": (dict(profile) if profile else None) if show_psych else None}