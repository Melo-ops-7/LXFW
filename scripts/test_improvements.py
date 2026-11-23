# -*- coding: utf-8 -*-
"""改进项验证：心情打卡/连续5天高危预警/画像权限/文案替换/课程列表/Dify真实链路。
运行：python scripts/test_improvements.py （需后端已在 8010 启动）
"""
import os
import sqlite3
import sys
from datetime import date, timedelta

import httpx

BASE = "http://localhost:8010"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "xinxifang.db")
passed, failed = [], []


def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(extra) if extra else ""))


c = httpx.Client(base_url=BASE, timeout=120)


def login(u, p):
    r = c.post("/api/auth/login", json={"username": u, "password": p})
    return r.json()["token"], r.json()["user"]


stu_token, stu = login("student2", "123456")
SH = {"Authorization": "Bearer " + stu_token}
tea_token, tea = login("teacher1", "123456")
TH = {"Authorization": "Bearer " + tea_token}

# 1) 心情打卡基础
r = c.post("/api/student/mood", headers=SH, json={"student_id": stu["id"], "mood": 1})
j = r.json()
check("心情打卡提交", r.status_code == 200 and j["mood"] == 1 and j["mood_date"] == date.today().isoformat(), j.get("message"))
r = c.get("/api/student/mood", headers=SH)
check("心情查询今日状态", r.json()["today"] == 1)
r = c.post("/api/student/mood", headers=SH, json={"student_id": stu["id"], "mood": 5})
check("非法心情值拒绝422", r.status_code == 422)

# 2) 分级预警：连续3天最差心情→关注级(中)，连续5天→高危(高)，同一预警升级不重复
stu3_token, stu3 = login("student3", "123456")
S3H = {"Authorization": "Bearer " + stu3_token}
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM student_mood WHERE student_id=?", (stu3["id"],))
conn.execute("DELETE FROM student_psych_alert WHERE student_id=? AND trigger_reason LIKE '心情打卡%'", (stu3["id"],))
for i in range(1, 3):  # 前2天很差
    d = (date.today() - timedelta(days=i)).isoformat()
    conn.execute("INSERT INTO student_mood(student_id,mood_date,mood) VALUES(?,?,4)", (stu3["id"], d))
conn.commit(); conn.close()
r = c.post("/api/student/mood", headers=S3H, json={"student_id": stu3["id"], "mood": 4})
j = r.json()
check("连续3天最差心情→关注级", j["streak"] == 3 and j["watch"] and j["risk_level"] == "中" and not j["alerted"], j.get("message"))
watch_id = j["alert_id"]
r = c.get("/api/student/alerts", headers=TH, params={"student_id": stu3["id"]})
ma = next((a for a in r.json() if a["trigger_reason"].startswith("心情打卡")), None)
check("班主任可见关注级预警(中)", ma is not None and ma["risk_level"] == "中" and ma["teacher_id"], ma and ma["trigger_reason"])
r = c.post("/api/student/mood", headers=S3H, json={"student_id": stu3["id"], "mood": 4})
check("关注级重复打卡不重复预警", r.json()["alert_id"] == watch_id)
conn = sqlite3.connect(DB)
for i in range(3, 5):  # 补到连续5天
    d = (date.today() - timedelta(days=i)).isoformat()
    conn.execute("INSERT INTO student_mood(student_id,mood_date,mood) VALUES(?,?,4)", (stu3["id"], d))
conn.commit(); conn.close()
r = c.post("/api/student/mood", headers=S3H, json={"student_id": stu3["id"], "mood": 4})
j = r.json()
check("连续5天最差心情→高危升级", j["streak"] == 5 and j["alerted"] and j["risk_level"] == "高" and j["alert_id"] == watch_id, j.get("message"))
r = c.get("/api/student/alerts", headers=TH, params={"student_id": stu3["id"]})
ma = next((a for a in r.json() if a["trigger_reason"].startswith("心情打卡")), None)
check("预警已升级为高危且仅一条", ma is not None and ma["risk_level"] == "高" and
      sum(1 for a in r.json() if a["trigger_reason"].startswith("心情打卡")) == 1)
r = c.post("/api/student/mood", headers=S3H, json={"student_id": stu3["id"], "mood": 4})
check("高危后重复打卡不重复预警", r.json()["alert_id"] == watch_id and not r.json()["alerted"])

# 3) 画像权限：学生不可见，班主任可见
r = c.get("/api/student/psych-profile", headers=SH, params={"student_id": stu["id"]})
check("学生访问心理画像拒绝403", r.status_code == 403)
r = c.get("/api/student/overview", headers=SH, params={"student_id": stu["id"]})
check("学生总览不含心理画像", r.json()["psych_profile"] is None)

# 4) 降级兜底：课程列表两个热门项目+引导语；无禁用文案
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from dify_client import local_fallback
reply = local_fallback("service", "你们有哪些课程？", {})
check("降级课程列表含两热门项目", "0.5/1+2新加坡定向培养本科班" in reply and "德国双元制精英人才共建计划" in reply)
check("降级课程列表含引导语", "留学项目" in reply and "按钮" in reply)
for agent, msg in [("service", "你们公司年会是哪天？"), ("student", "宿舍几点关门？"), ("employee", "报销流程是什么？")]:
    rp = local_fallback(agent, msg, {"student_id": stu["id"], "employee_id": tea["id"]})
    check(f"降级{agent}无禁用文案", "资料中未明确" not in rp and "暂未单独收录" not in rp and "暂未收录" not in rp, rp[:50])

# 5) Dify 真实链路：课程列表 + 未知信息文案
r = c.post("/api/chat/service", json={"message": "你们有哪些课程？", "session_key": "improve-test"})
j = r.json()
check("Dify课程列表含两热门项目", "0.5/1+2" in j["reply"] and "德国双元制" in j["reply"], j["reply"][:80])
check("Dify课程列表含引导语", "留学项目" in j["reply"] and "按钮" in j["reply"], j["reply"][-80:])
r = c.post("/api/chat/service", json={"message": "你们公司年会在哪一天举办？", "session_key": "improve-test"})
j = r.json()
check("Dify未知信息用新文案", "可进一步联系我们工作人员确认" in j["reply"], j["reply"][:80])
check("Dify回复无禁用文案", "资料中未明确" not in j["reply"] and "暂未单独收录" not in j["reply"] and "暂未收录" not in j["reply"], j["reply"][:80])

print("\n========== 结果 ==========")
print(f"通过 {len(passed)} / {len(passed) + len(failed)}")
if failed:
    print("失败项：", failed)
    sys.exit(1)
print("全部改进项验证通过 ✔")