"""Dify API 客户端 + 本地降级（需求 11.1 外部服务异常）。

- 通过 /chat-messages 调用三个 Agent 应用，conversation_id 续接上下文；
- Dify 不可用/未配置 Key 时降级为本地规则应答（情绪/请假/NL2SQL/FAQ 检索）。
"""
import json
import re

import httpx

import config
from database import db


def _clean_answer(answer: str) -> str:
    """清洗推理模型输出：只保留 </think> 之后的正式回答，去除推理标记。"""
    if not answer:
        return answer
    if "</think>" in answer:
        answer = answer.split("</think>")[-1]
    answer = answer.replace("<!--dify-deepseek-reasoning-->", "")
    answer = re.sub(r"^<think>[\s\S]*?(?:</think>|$)", "", answer.strip())
    return answer.strip()


def call_dify(agent_type: str, message: str, user_key: str,
              inputs: dict, conversation_id: str = None):
    """返回 (reply, conversation_id, degraded, meta)。"""
    api_key = config.DIFY_API_KEYS.get(agent_type, "")
    if not api_key:
        reply = local_fallback(agent_type, message, inputs)
        return reply, conversation_id, True, {"reason": "未配置 Dify API Key，使用本地规则应答"}
    payload = {"inputs": inputs or {}, "query": message, "user": user_key,
               "response_mode": "blocking"}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    try:
        resp = httpx.post(
            f"{config.DIFY_BASE_URL.rstrip('/')}/chat-messages",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        answer = _clean_answer(data.get("answer") or "")
        if not answer:
            raise ValueError("Dify 返回空回答")
        return answer, data.get("conversation_id") or conversation_id, False, {
            "message_id": data.get("message_id"),
            "retriever_resources": (data.get("metadata") or {}).get("retriever_resources"),
        }
    except Exception as exc:  # 降级：隐藏内部错误细节
        reply = local_fallback(agent_type, message, inputs)
        return reply, conversation_id, True, {"reason": f"Dify 调用失败，已降级本地规则应答"}


# ---------- 本地 FAQ 检索（知识库兜底） ----------
_faq_cache = None


def _load_faq():
    global _faq_cache
    if _faq_cache is None:
        try:
            _faq_cache = json.loads(config.FAQ_JSON.read_text(encoding="utf-8"))
        except Exception:
            _faq_cache = []
    return _faq_cache


def faq_search(question: str):
    """字符二元组重合度评分，返回最佳 FAQ 答案（无匹配返回 None）。"""
    faq = _load_faq()
    if not faq or not question:
        return None

    def grams(s):
        s = re.sub(r"[^\w一-龥]", "", s)
        return {s[i:i + 2] for i in range(len(s) - 1)} or {s}

    qg = grams(question)
    best, best_score = None, 0.0
    for item in faq:
        fg = grams(item["q"])
        score = len(qg & fg) / max(1, len(qg))
        if score > best_score:
            best, best_score = item, score
    return best["a"] if best_score >= 0.35 else None


def local_fallback(agent_type: str, message: str, inputs: dict) -> str:
    """脱离 Dify 的确定性降级应答。"""
    inputs = inputs or {}
    if agent_type == "student":
        return _student_fallback(message, inputs)
    if agent_type == "employee":
        return _employee_fallback(message, inputs)
    return _service_fallback(message, inputs)


def _student_fallback(message, inputs):
    from rules import emotion as emotion_rules
    from rules import leave_parser
    student_id = inputs.get("student_id")
    parts = []
    # 情绪评估始终执行（心理关怀兜底）
    if student_id:
        ev = emotion_rules.evaluate(message)
        if ev["alerted"]:
            parts.append("【高危预警】已识别到高危情绪信号，已通知班主任尽快关注你。"
                         "如需紧急帮助，请拨打心理援助热线 12356。")
        elif ev["emotion_score"] >= 40:
            parts.append("我注意到你最近有些压力，已记录你的情绪状态。愿意和我多聊聊吗？")
    if re.search(r"请假", message) and student_id:
        start, end, parsed = leave_parser.parse_leave_time(message)
        with db() as conn:
            conn.execute(
                "INSERT INTO student_admin_service(student_id,service_type,start_time,end_time,reason,status) "
                "VALUES(?,?,?,?,?,'待审批')", (student_id, "请假", start, end, message))
        parts.append(f"请假申请已提交：{start} 至 {end}，状态「待审批」，等待班主任审批。")
    elif re.search(r"成绩|分数", message) and student_id:
        with db() as conn:
            rows = conn.execute("SELECT course_name,score,semester FROM student_score WHERE student_id=?",
                                (student_id,)).fetchall()
        parts.append("你的成绩：\n" + "\n".join(f"- {r['course_name']}：{r['score']}分" for r in rows)
                     if rows else "暂无成绩记录。")
    elif re.search(r"投诉|反馈|报修", message) and student_id:
        with db() as conn:
            conn.execute("INSERT INTO student_feedback_ticket(student_id,content,detail,status) "
                         "VALUES(?,?,?,'待处理')", (student_id, message[:50], message))
        parts.append("反馈工单已提交，状态「待处理」，老师解决后会通知你。")
    else:
        faq = faq_search(message)
        if faq:
            parts.append(faq)
    if not parts:
        parts.append("你好，我是新西方留学服务学生智能管家。可以帮你：请假申请、成绩查询、售后反馈、心理关怀与升学咨询。")
    return "\n\n".join(parts) + "\n\n（提示：智能编排服务暂不可用，当前为本地规则应答。）"


def _employee_fallback(message, inputs):
    from rules import nl2sql
    result = nl2sql.process(message, inputs.get("employee_id"))
    lines = [f"【意图】{result['intent']}", result["message"]]
    if result["results"]:
        lines.append("```json\n" + json.dumps(result["results"][:10], ensure_ascii=False, indent=2) + "\n```")
    return "\n".join(lines) + "\n\n（提示：智能编排服务暂不可用，当前为本地规则应答。）"


def _service_fallback(message, inputs):
    from rules import profile as profile_rules
    if re.search(r"哪些课程|有什么课程|课程有哪些|哪些项目|项目有哪些|有什么项目|课程列表|全部课程|都有什么课", message):
        return ("我们的热门项目有：\n"
                "1. **0.5/1+2新加坡定向培养本科班**：适合高中毕业生（约16-19岁），国内预科+新加坡就读，"
                "2.5/3年学费总计约25万-26万元人民币，学历回国受中国教育部认证。\n"
                "2. **德国双元制精英人才共建计划**：免学费，培训期间享津贴（约880-1030欧/月），"
                "2-3.5年考取IHK/HWK职业资格证书后可就业或升学。\n\n"
                "还有更多课程可以点击官网上方「留学项目」按钮查看。")
    if re.search(r"推荐|适合|匹配|方案", message) or re.search(r"\d{1,2}岁", message):
        result = profile_rules.analyze(message)
        if result["best_match"]:
            b = result["best_match"]
            return (f"推荐【{b['project']}】，匹配度{b['score']}分。\n理由：{b['reason']}\n"
                    "如需了解学费与报名流程，欢迎留下姓名与联系方式。")
        if result.get("message"):
            return result["message"]
    if re.search(r"报名", message):
        return "报名请提供活动名称与您的姓名、联系方式，例如「报名新加坡留学分享会，张三，13800000000」。"
    faq = faq_search(message)
    if faq:
        return faq + "\n\n（提示：智能编排服务暂不可用，当前为本地知识库应答。）"
    return ("您好，我是新西方留学服务智能客服。可以为您解答公司信息、留学政策、项目费用、常见问题，"
            "也可以推荐留学项目、查询与报名活动。请问有什么可以帮您？")