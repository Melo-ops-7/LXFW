"""对话代理路由：前端 → 后端 → Dify（上下文续接 + 对话沉淀 + 降级）。

Dify API Key 仅保存在后端，不暴露给浏览器（需求 12.3）。
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

import auth
import dify_client
import schemas
from database import db, rows_to_dicts
from rules import emotion as emotion_rules

router = APIRouter(prefix="/api/chat", tags=["对话代理"])
AGENTS = {"student", "employee", "service"}


def _user_key(user, session_key):
    if user and user["user_type"] in ("STUDENT", "EMPLOYEE"):
        return f"{user['user_type'].lower()}_{user['id']}"
    return f"guest_{session_key or uuid.uuid4().hex[:12]}"


def _inputs(agent_type, user):
    if agent_type == "student" and user and user["user_type"] == "STUDENT":
        return {"student_id": str(user["id"]), "user_name": user["real_name"]}
    if agent_type == "employee" and user and user["user_type"] == "EMPLOYEE":
        return {"employee_id": str(user["id"]), "employee_role": user.get("employee_role") or "",
                "user_name": user["real_name"]}
    return {"user_name": user["real_name"] if user else "访客"}


def _latest_conversation(user_key, agent_type):
    with db() as conn:
        row = conn.execute(
            "SELECT dify_conversation_id FROM conversation_log "
            "WHERE user_id=? AND agent_type=? ORDER BY id DESC LIMIT 1",
            (user_key, agent_type)).fetchone()
    return row["dify_conversation_id"] if row else None


@router.get("/history", summary="查询本人对话历史")
def history(agent_type: str, limit: int = 50, session_key: str = None,
            user=Depends(auth.optional_user)):
    if agent_type not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    user_key = _user_key(user, session_key)
    with db() as conn:
        rows = rows_to_dicts(conn.execute(
            "SELECT id,user_input,ai_reply,emotion_tag,create_time FROM conversation_log "
            "WHERE user_id=? AND agent_type=? ORDER BY id DESC LIMIT ?",
            (user_key, agent_type, limit)).fetchall())
    return list(reversed(rows))


@router.post("/reset", summary="重置对话上下文")
def reset(agent_type: str, session_key: str = None, user=Depends(auth.optional_user)):
    if agent_type not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    user_key = _user_key(user, session_key)
    with db() as conn:
        conn.execute(
            "INSERT INTO conversation_log(user_id,agent_type,user_input,ai_reply,dify_conversation_id) "
            "VALUES(?,?,?,NULL,NULL)", (user_key, agent_type, "[上下文已重置]"))
    return {"message": "上下文已重置，下一轮将开启新会话。"}


@router.post("/{agent_type}", summary="与指定 Agent 对话（自动续接上下文）")
def chat(agent_type: str, body: schemas.ChatIn, user=Depends(auth.optional_user)):
    if agent_type not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent_type == "student" and (not user or user["user_type"] != "STUDENT"):
        raise HTTPException(status_code=401, detail="学生管家需要学生登录")
    if agent_type == "employee" and (not user or user["user_type"] != "EMPLOYEE"):
        raise HTTPException(status_code=401, detail="员工助手需要员工登录")

    user_key = _user_key(user, body.session_key)
    inputs = _inputs(agent_type, user)
    conversation_id = _latest_conversation(user_key, agent_type)
    reply, new_conv, degraded, meta = dify_client.call_dify(
        agent_type, body.message, user_key, inputs, conversation_id)

    emotion_tag = None
    if agent_type == "student":
        emotion_tag = emotion_rules.evaluate(body.message)["emotion_tag"]
    with db() as conn:
        conn.execute(
            "INSERT INTO conversation_log(user_id,agent_type,user_input,ai_reply,emotion_tag,dify_conversation_id) "
            "VALUES(?,?,?,?,?,?)",
            (user_key, agent_type, body.message, reply, emotion_tag, new_conv))
    return {"reply": reply, "conversation_id": new_conv, "degraded": degraded,
            "meta": meta, "session_key": user_key.replace("guest_", "") if user_key.startswith("guest_") else None}