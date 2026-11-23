# -*- coding: utf-8 -*-
"""验收自测脚本：覆盖 ACC-001 ~ ACC-010（需求规格说明书 17 章）。
运行：python scripts/test_api.py  （需后端已在 8000 端口启动）
"""
import sys
import httpx

BASE = "http://localhost:8010"
KEY = "xinxifang-tool-key-2026"
H = {"X-API-Key": KEY}
passed, failed = [], []


def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra else ""))


c = httpx.Client(base_url=BASE, timeout=30)

# 健康检查
r = c.get("/api/health")
check("FR-030 健康检查", r.status_code == 200 and r.json()["status"] == "ok")

# ACC-001 画像研判
r = c.post("/api/profile/analyze", headers=H, json={"raw_text": "我家孩子19岁、高中刚毕业、想快点拿本科学历"})
j = r.json()
check("ACC-001 画像研判(19岁高中→0.5/1+2, 93分)",
      j["best_match"] and j["best_match"]["project"] == "0.5/1+2新加坡定向培养本科班" and j["best_match"]["score"] == 93,
      j["best_match"])
check("FR-001 目标学历不误判(education=高中)", j["profile"]["education"] == "高中", j["profile"])

# 画像：就业导向 / 双元制 / 无匹配
r = c.post("/api/profile/analyze", headers=H, json={"raw_text": "中职技校毕业，17岁，想尽快就业"})
j = r.json()
check("FR-004 就业导向(6+6/9+6命中)", any("6+6" in m["project"] for m in j["matches"]), [m["project"] for m in j["matches"]])
r = c.post("/api/profile/analyze", headers=H, json={"raw_text": "28岁本科毕业，有德语B1基础，动手能力强，想移民德国"})
j = r.json()
check("FR-004 德国双元制(18-35+德语+动手)", any("双元制" in m["project"] for m in j["matches"]), [m["project"] for m in j["matches"]])
r = c.post("/api/profile/analyze", headers=H, json={"raw_text": "我想了解一下"})
j = r.json()
check("ACC-009 画像不足明确提示", j["best_match"] is None and "不足" in j["message"], j["message"])

# 登录
r = c.post("/api/auth/login", json={"username": "student1", "password": "123456"})
stu_token = r.json()["token"]; stu_id = r.json()["user"]["id"]
SH = {"Authorization": "Bearer " + stu_token}
r = c.post("/api/auth/login", json={"username": "teacher1", "password": "123456"})
tea_token = r.json()["token"]; tea_id = r.json()["user"]["id"]
TH = {"Authorization": "Bearer " + tea_token}
r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
adm_token = r.json()["token"]
AH = {"Authorization": "Bearer " + adm_token}
r = c.post("/api/auth/login", json={"username": "consultant1", "password": "123456"})
con_token = r.json()["token"]; con_id = r.json()["user"]["id"]
CH = {"Authorization": "Bearer " + con_token}
check("登录鉴权(4角色)", all([stu_token, tea_token, adm_token, con_token]))
r = c.post("/api/auth/login", json={"username": "student1", "password": "wrong"})
check("错误密码拒绝", r.status_code == 401)

# ACC-005 请假申请（时间兜底解析）
r = c.post("/api/student/leave", headers=SH, json={"student_id": stu_id, "reason": "我明天要请假一天，家里有事"})
j = r.json()
check("ACC-005 请假解析+待审批", r.status_code == 200 and j["status"] == "待审批" and j["time_parsed"], (j["start_time"], j["end_time"]))
leave_id = j["id"]
r = c.post("/api/student/leave", headers=SH, json={"student_id": stu_id, "reason": "后天请假半天去看病"})
check("FR-006 半天解析", r.json()["time_parsed"] and r.json()["end_time"].endswith("12:00:00"))

# ACC-010 权限：学生不能审批
r = c.post("/api/student/leave/approve", headers=SH, json={"leave_id": leave_id, "approved": True})
check("ACC-010 学生无审批权限(403)", r.status_code == 403)
# FR-008 班主任审批
r = c.post("/api/student/leave/approve", headers=TH, json={"leave_id": leave_id, "approver_id": tea_id, "approved": True})
check("FR-008 班主任审批通过", r.json()["status"] == "已通过")
r = c.post("/api/student/leave/approve", headers=TH, json={"leave_id": 99999, "approved": True})
check("ACC-010 审批不存在404", r.status_code == 404)

# ACC-002 心理预警
r = c.post("/api/student/emotion", headers=SH, json={"student_id": stu_id, "text": "最近压力好大，感觉活不下去了"})
j = r.json()
check("ACC-002 高危预警(90分+已通知班主任)", j["emotion_score"] == 90 and j["alerted"] and "班主任" in j["message"], j)
alert_id = j["alert_id"]
r = c.get("/api/student/alerts", headers=TH, params={"status": "未处理"})
check("FR-011 预警列表可查", any(a["id"] == alert_id for a in r.json()))
r = c.post(f"/api/student/alerts/{alert_id}/status", headers=TH, json={"status": "跟进中", "teacher_id": tea_id})
check("FR-011 预警状态更新", r.json()["status"] == "跟进中")
r = c.get("/api/student/psych-profile", headers=SH, params={"student_id": stu_id})
check("心理画像学生本人不可见403", r.status_code == 403)
r = c.get("/api/student/psych-profile", headers=TH, params={"student_id": stu_id})
j = r.json()
check("FR-010 心理画像upsert+历史(班主任可见)", j["emotion_score"] == 90 and len(j["emotion_history"]) >= 1)
r = c.post("/api/student/emotion", headers=SH, json={"student_id": stu_id, "text": "今天很开心，课程很顺利"})
check("FR-009 积极情绪15分", r.json()["emotion_score"] == 15 and not r.json()["alerted"])

# FR-012/014 工单
r = c.post("/api/student/feedback", headers=SH, json={"student_id": stu_id, "content": "签证材料进度慢", "detail": "希望加快"})
ticket_id = r.json()["id"]
check("FR-012 工单待处理", r.json()["status"] == "待处理")
r = c.post(f"/api/student/feedback/{ticket_id}/resolve", headers=TH, json={"solution": "已加急处理完毕"})
j = r.json()
check("FR-014 解决+已通知", j["status"] == "已解决" and j["is_notified"] == 1)
r = c.post("/api/student/feedback/99999/resolve", headers=TH, json={"solution": "x"})
check("ACC-010 工单不存在404", r.status_code == 404)

# FR-015 学生成绩
r = c.get("/api/student/scores", headers=SH)
check("FR-015 学生查本人成绩", r.status_code == 200 and len(r.json()) >= 1)

# ACC-003 NL2SQL
r = c.post("/api/employee/nl2sql", headers=CH, json={"text": "帮我查一下许同学的跟进记录", "employee_id": con_id})
j = r.json()
check("ACC-003 NL2SQL查许同学", j["intent"] == "查客户" and j["results"] and j["results"][0]["customer_name"] == "许同学", j["message"])
r = c.post("/api/employee/nl2sql", headers=CH, json={"text": "把许同学状态更新为已签约", "employee_id": con_id})
check("FR-022 NL2SQL更新客户状态", r.json()["intent"] == "更新客户状态" and r.json()["results"][0]["status"] == "已签约")
r = c.post("/api/employee/nl2sql", headers=CH, json={"text": "查一下张三的成绩", "employee_id": con_id})
check("FR-022 NL2SQL查成绩", r.json()["intent"] == "查成绩" and len(r.json()["results"]) >= 1)
r = c.post("/api/employee/nl2sql", headers=CH, json={"text": "今天天气怎么样", "employee_id": con_id})
check("FR-022 未识别指令提示支持列表", r.json()["intent"] == "未识别" and "支持" in r.json()["message"])

# ACC-006 CRM 流转
r = c.get("/api/employee/leads", headers=CH, params={"keyword": "许同学"})
lead_id = r.json()[0]["id"]
r = c.post(f"/api/employee/leads/{lead_id}/status", headers=CH, json={"status": "跟进中"})
check("ACC-006 合法状态流转", r.json()["status"] == "跟进中")
r = c.post(f"/api/employee/leads/{lead_id}/status", headers=CH, json={"status": "随便的状态"})
check("ACC-006 非法状态400", r.status_code == 400)
r = c.get("/api/employee/leads/99999", headers=CH)
check("ACC-010 客户不存在404", r.status_code == 404)

# FR-016 录客户 / FR-019 日报 / FR-020 录成绩
r = c.post("/api/employee/leads", headers=CH, json={"customer_name": "测试家长", "contact_info": "13911112222", "background_info": "自测录入", "owner_employee_id": con_id})
check("FR-016 录客户新增意向", r.json()["status"] == "新增意向")
r = c.post("/api/employee/reports", headers=CH, json={"employee_id": con_id, "content": "自测日报"})
check("FR-019 日报默认当天", r.json()["report_date"])
r = c.post("/api/employee/scores", headers=TH, json={"student_id": stu_id, "course_name": "自测课程", "score": 99.5, "semester": "2026秋季"})
check("FR-020 成绩录入", r.json()["score"] == 99.5)

# ACC-004 活动报名（唯一客户名，保证脚本可重复执行）
import time
_suffix = str(int(time.time()))[-6:]
r = c.get("/api/events")
events = r.json()
open_ev = next(e for e in events if not e["is_full"])
full_ev = next(e for e in events if e["is_full"])
before = open_ev["current_participants"]
r = c.post("/api/events/register", json={"event_id": open_ev["id"], "customer_name": "自测客户" + _suffix, "contact_info": "139" + _suffix + "00"})
j = r.json()
check("ACC-004 报名成功+人数+1", r.status_code == 200 and j["current_participants"] == before + 1, j["message"])
r = c.post("/api/events/register", json={"event_id": full_ev["id"], "customer_name": "自测客户2"})
check("ACC-004 名额已满400", r.status_code == 400)
r = c.post("/api/events/register", json={"event_id": 99999, "customer_name": "x"})
check("ACC-010 活动不存在404", r.status_code == 404)
r = c.get("/api/events/registrations", params={"event_id": open_ev["id"]})
check("FR-027 报名记录含活动名", any(x["event_name"] == open_ev["event_name"] for x in r.json()))

# FR-023/024 课程查询与推荐
r = c.get("/api/courses", params={"keyword": "新加坡"})
check("FR-023 课程关键词查询", len(r.json()) >= 5)
r = c.post("/api/courses/recommend", json={"raw_text": "19岁高中毕业想拿本科学历"})
j = r.json()
check("FR-024 推荐附关键信息(不编造)", j["best_match"]["detail"] and "25万" in j["best_match"]["detail"]["description"])

# ACC-008 降级应答（直接验证本地降级函数，与 Dify 是否在线解耦）
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from dify_client import local_fallback
reply = local_fallback("service", "新加坡2+2四年学费多少？", {})
check("ACC-008 客服降级FAQ应答", "30" in reply, reply[:60])
reply = local_fallback("student", "我明天要请假一天", {"student_id": stu_id})
check("ACC-008 学生降级请假应答", "待审批" in reply, reply[:60])
reply = local_fallback("employee", "帮我查一下许同学的跟进记录", {"employee_id": con_id})
check("ACC-008 员工降级NL2SQL应答", "许同学" in reply, reply[:60])
# 在线对话链路（Dify 已配置时走真实编排，未配置时自动降级，两者均应 200 且有回复）
r = c.post("/api/chat/service", json={"message": "新加坡2+2四年学费多少？", "session_key": "selftest"}, timeout=120)
check("ACC-008 在线对话链路可用", r.status_code == 200 and len(r.json()["reply"]) > 10, r.json()["reply"][:60])
# 上下文续接字段
r = c.post("/api/chat/service", json={"message": "那德国项目呢？", "session_key": "selftest"}, timeout=120)
check("对话上下文映射持久化", "conversation_id" in r.json())
r = c.get("/api/chat/history", params={"agent_type": "service", "session_key": "selftest"})
check("FR-029 对话沉淀可查", len(r.json()) >= 2)

# 管理后台
r = c.get("/api/admin/overview", headers=AH)
check("FR-031 后台总览", r.json()["leads_total"] >= 4)
r = c.get("/api/admin/overview", headers=CH)
check("ACC-010 顾问无后台权限403", r.status_code == 403)
r = c.get("/api/admin/users", headers=AH)
check("用户管理列表", len(r.json()) >= 8)
r = c.get("/api/admin/system", headers=AH)
check("系统健康状态", r.json()["backend"] == "ok")

# 无鉴权拒绝
r = c.get("/api/employee/leads")
check("未登录访问拒绝401", r.status_code == 401)
r = c.get("/api/employee/leads", headers={"X-API-Key": "wrong"})
check("错误API Key拒绝401", r.status_code == 401)

print("\n========== 结果 ==========")
print(f"通过 {len(passed)} / {len(passed) + len(failed)}")
if failed:
    print("失败项：", failed)
    sys.exit(1)
print("全部验收项通过 ✔")