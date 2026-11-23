"""NL2SQL 指令处理（FR-022，需求 ACC-003）。

确定性意图识别 + 参数化 SQL（白名单表，防注入）：
查成绩 / 录成绩 / 查日报 / 写日报 / 查客户 / 录客户 / 更新客户状态 /
查投诉 / 更新投诉状态 / 审批请假 / 查请假。
识别不到实体时明确提示，不猜测；未识别指令返回支持列表。
"""
import json
import re
from datetime import datetime

from database import db, rows_to_dicts

SUPPORTED = ("查成绩、录成绩、查日报、写日报、查客户、录客户、更新客户状态、"
             "查投诉、更新投诉状态、审批请假、查请假")

LEAD_STATUSES = ["新增意向", "跟进中", "已签约", "已流失"]
TICKET_STATUSES = ["待处理", "处理中", "已解决"]


def _display_sql(sql, params):
    """仅用于展示：把参数安全回填到 SQL 文本。"""
    out = sql
    for p in params:
        v = f"'{p}'" if isinstance(p, str) else str(p)
        out = out.replace("?", v, 1)
    return out


def _find_student(conn, text):
    m = re.search(r"([一-龥]{1,4}同学)", text)
    if m:
        name = m.group(1).replace("同学", "")
        row = conn.execute("SELECT * FROM sys_user WHERE user_type='STUDENT' AND real_name LIKE ?",
                           (f"%{name}%",)).fetchone()
        if row:
            return dict(row)
    for row in conn.execute("SELECT * FROM sys_user WHERE user_type='STUDENT'").fetchall():
        if row["real_name"] in text:
            return dict(row)
    return None


def _find_lead(conn, text):
    m = re.search(r"([一-龥]{1,4}(?:同学|先生|女士|家长))", text)
    if m:
        row = conn.execute("SELECT * FROM crm_lead WHERE customer_name LIKE ?",
                           (f"%{m.group(1)}%",)).fetchone()
        if row:
            return dict(row)
    for row in conn.execute("SELECT * FROM crm_lead").fetchall():
        if row["customer_name"] in text:
            return dict(row)
    return None


def _ok(intent, sql, params, results, message):
    return {"intent": intent, "sql": _display_sql(sql, params),
            "results": results, "message": message}


def _miss(intent, message):
    return {"intent": intent, "sql": None, "results": [], "message": message}


def process(text: str, employee_id: int = None) -> dict:
    text = (text or "").strip()
    if not text:
        return _miss("未识别", f"未识别到有效指令。支持：{SUPPORTED}。")
    now = datetime.now()

    with db() as conn:
        # ---------- 审批请假 ----------
        if re.search(r"(同意|通过|批准|驳回|拒绝).{0,12}请假", text):
            approved = not re.search(r"驳回|拒绝", text)
            student = _find_student(conn, text)
            if not student:
                return _miss("审批请假", "未识别到学生姓名，请说明要审批哪位学生的请假，如「同意张三的请假申请」。")
            row = conn.execute(
                "SELECT * FROM student_admin_service WHERE student_id=? AND service_type='请假' "
                "AND status='待审批' ORDER BY id DESC LIMIT 1", (student["id"],)).fetchone()
            if not row:
                return _miss("审批请假", f"未找到{student['real_name']}的待审批请假申请。")
            new_status = "已通过" if approved else "已驳回"
            sql = "UPDATE student_admin_service SET status=?, approver_id=?, update_time=? WHERE id=?"
            params = [new_status, employee_id, now.strftime("%Y-%m-%d %H:%M:%S"), row["id"]]
            conn.execute(sql, params)
            return _ok("审批请假", sql, params, [{"id": row["id"], "student": student["real_name"],
                                                 "status": new_status}],
                       f"已将{student['real_name']}的请假申请（第{row['id']}号）审批为「{new_status}」。")

        # ---------- 更新客户状态 ----------
        m = re.search(r"(新增意向|跟进中|已签约|已流失)", text)
        if m and re.search(r"客户|线索|状态", text) and re.search(r"更新|改为|改成|流转|标记|变为|设为", text):
            lead = _find_lead(conn, text)
            if not lead:
                return _miss("更新客户状态", "未识别到客户姓名，请说明要更新哪位客户，如「把许同学状态更新为已签约」。")
            status = m.group(1)
            sql = "UPDATE crm_lead SET status=?, update_time=? WHERE id=?"
            params = [status, now.strftime("%Y-%m-%d %H:%M:%S"), lead["id"]]
            conn.execute(sql, params)
            return _ok("更新客户状态", sql, params,
                       [{"id": lead["id"], "customer_name": lead["customer_name"], "status": status}],
                       f"客户「{lead['customer_name']}」状态已更新为「{status}」。")

        # ---------- 更新投诉状态 ----------
        m = re.search(r"(待处理|处理中|已解决)", text)
        if m and re.search(r"投诉|工单|反馈", text) and re.search(r"更新|改为|改成|标记|设为|跟进", text):
            student = _find_student(conn, text)
            status = m.group(1)
            if student:
                row = conn.execute(
                    "SELECT * FROM student_feedback_ticket WHERE student_id=? AND status!='已解决' "
                    "ORDER BY id DESC LIMIT 1", (student["id"],)).fetchone()
            else:
                mid = re.search(r"(?:工单|投诉)\s*(?:第)?\s*(\d+)", text)
                row = conn.execute("SELECT * FROM student_feedback_ticket WHERE id=?",
                                   (int(mid.group(1)),)).fetchone() if mid else None
            if not row:
                return _miss("更新投诉状态", "未找到对应工单，请说明学生姓名或工单编号，如「把李四的投诉状态更新为处理中」。")
            sql = "UPDATE student_feedback_ticket SET status=?, update_time=? WHERE id=?"
            params = [status, now.strftime("%Y-%m-%d %H:%M:%S"), row["id"]]
            conn.execute(sql, params)
            return _ok("更新投诉状态", sql, params, [{"id": row["id"], "status": status}],
                       f"工单第{row['id']}号状态已更新为「{status}」。")

        # ---------- 录成绩 ----------
        if re.search(r"(录入|记录|登记|添加).{0,8}成绩", text):
            student = _find_student(conn, text)
            mscore = re.search(r"(\d+(?:\.\d+)?)\s*分", text)
            mcourse = re.search(r"(?:课程|科目)[：:\s]*([一-龥A-Za-z（）()]+)", text)
            if not mcourse:
                mcourse = re.search(r"录入([一-龥A-Za-z（）()]{2,12}?)成绩", text)
            if not student or not mscore:
                return _miss("录成绩", "信息不足：请提供学生姓名与分数，如「给张三录入英语成绩88分」。")
            course = mcourse.group(1) if mcourse else "未命名课程"
            sql = "INSERT INTO student_score(student_id,course_name,score,semester) VALUES(?,?,?,?)"
            params = [student["id"], course, float(mscore.group(1)), None]
            cur = conn.execute(sql, params)
            return _ok("录成绩", sql, params,
                       [{"id": cur.lastrowid, "student": student["real_name"],
                         "course_name": course, "score": float(mscore.group(1))}],
                       f"已录入{student['real_name']}的{course}成绩：{mscore.group(1)}分。")

        # ---------- 查成绩 ----------
        if re.search(r"查.{0,10}(成绩|分数)", text) or re.search(r"(成绩|分数).{0,6}(查|多少)", text):
            student = _find_student(conn, text)
            if not student:
                return _miss("查成绩", "未识别到学生姓名，请说明要查询哪位学生的成绩，如「查一下张三的成绩」。")
            sql = "SELECT * FROM student_score WHERE student_id=? ORDER BY id DESC"
            rows = rows_to_dicts(conn.execute(sql, (student["id"],)).fetchall())
            return _ok("查成绩", sql, [student["id"]], rows,
                       f"{student['real_name']}共有{len(rows)}条成绩记录。" if rows
                       else f"未找到{student['real_name']}的成绩记录。")

        # ---------- 写日报 ----------
        if re.search(r"(写|提交|记录|口述|汇报).{0,6}日报", text) or text.startswith("日报"):
            if not employee_id:
                return _miss("写日报", "缺少员工身份，无法记录日报。")
            content = re.sub(r"^(帮我|请|我要|我想)?(写|提交|记录|口述|汇报)?(一下|今天的?)?日报[：:，,]?", "", text).strip() or text
            sql = "INSERT INTO employee_daily_report(employee_id,report_date,content) VALUES(?,?,?)"
            params = [employee_id, now.strftime("%Y-%m-%d"), content]
            cur = conn.execute(sql, params)
            return _ok("写日报", sql, params,
                       [{"id": cur.lastrowid, "report_date": params[1], "content": content}],
                       "今日日报已记录。")

        # ---------- 查日报 ----------
        if re.search(r"查.{0,10}日报", text) or re.search(r"日报.{0,6}(查|汇总)", text):
            sql = "SELECT r.*, u.real_name AS employee_name FROM employee_daily_report r " \
                  "LEFT JOIN sys_user u ON u.id=r.employee_id"
            params = []
            if employee_id and not re.search(r"所有|全部|团队|大家", text):
                sql += " WHERE r.employee_id=?"
                params.append(employee_id)
            sql += " ORDER BY r.report_date DESC, r.id DESC LIMIT 20"
            rows = rows_to_dicts(conn.execute(sql, params).fetchall())
            return _ok("查日报", sql, params, rows,
                       f"共查询到{len(rows)}条日报。" if rows else "未找到日报记录。")

        # ---------- 录客户 ----------
        if re.search(r"(录入|新增|添加).{0,6}(客户|线索)", text):
            mname = re.search(r"(?:客户|线索)[：:\s]*([一-龥]{2,4}(?:同学|先生|女士|家长)?)", text)
            if not mname:
                mname = re.search(r"([一-龥]{2,4}(?:同学|先生|女士|家长))", text)
            mphone = re.search(r"(1\d{10})", text)
            if not mname:
                return _miss("录客户", "未识别到客户姓名，请提供姓名与联系方式，如「新增客户王家长，电话13900000000」。")
            background = re.sub(r"^(帮我|请)?(录入|新增|添加)(一个|一位)?(意向)?(客户|线索)[：:，,]?", "", text).strip()
            sql = ("INSERT INTO crm_lead(customer_name,contact_info,background_info,follow_up_history,"
                   "status,owner_employee_id) VALUES(?,?,?,?,?,?)")
            params = [mname.group(1), mphone.group(1) if mphone else None,
                      background, json.dumps([], ensure_ascii=False), "新增意向", employee_id or 2]
            cur = conn.execute(sql, params)
            return _ok("录客户", sql, params,
                       [{"id": cur.lastrowid, "customer_name": mname.group(1), "status": "新增意向"}],
                       f"客户「{mname.group(1)}」已录入，初始状态「新增意向」。")

        # ---------- 查客户 / 跟进记录 ----------
        if re.search(r"(查|查询|看看|调取).{0,12}(客户|跟进|线索)", text) or "跟进记录" in text:
            lead = _find_lead(conn, text)
            if lead:
                sql = "SELECT * FROM crm_lead WHERE id=?"
                rows = rows_to_dicts(conn.execute(sql, (lead["id"],)).fetchall())
                try:
                    rows[0]["follow_up_history"] = json.loads(rows[0]["follow_up_history"] or "[]")
                except (ValueError, TypeError):
                    pass
                return _ok("查客户", sql, [lead["id"]], rows,
                           f"已找到客户「{lead['customer_name']}」的档案与跟进记录。")
            # 无实体：按状态/关键词列表查询
            sql = "SELECT * FROM crm_lead"
            params, conds = [], []
            for st in LEAD_STATUSES:
                if st in text:
                    conds.append("status=?")
                    params.append(st)
                    break
            if conds:
                sql += " WHERE " + " AND ".join(conds)
            sql += " ORDER BY id DESC LIMIT 20"
            rows = rows_to_dicts(conn.execute(sql, params).fetchall())
            return _ok("查客户", sql, params, rows,
                       f"共{len(rows)}条客户记录。" if rows else "未找到匹配的客户，请提供客户姓名或状态。")

        # ---------- 查投诉 ----------
        if re.search(r"查.{0,10}(投诉|反馈|工单)", text):
            sql = "SELECT t.*, u.real_name AS student_name FROM student_feedback_ticket t " \
                  "LEFT JOIN sys_user u ON u.id=t.student_id"
            params, conds = [], []
            student = _find_student(conn, text)
            if student:
                conds.append("t.student_id=?")
                params.append(student["id"])
            for st in TICKET_STATUSES:
                if st in text:
                    conds.append("t.status=?")
                    params.append(st)
                    break
            if conds:
                sql += " WHERE " + " AND ".join(conds)
            sql += " ORDER BY t.id DESC LIMIT 20"
            rows = rows_to_dicts(conn.execute(sql, params).fetchall())
            return _ok("查投诉", sql, params, rows,
                       f"共{len(rows)}条工单。" if rows else "未找到匹配的投诉工单。")

        # ---------- 查请假 ----------
        if re.search(r"查.{0,10}请假", text):
            sql = "SELECT s.*, u.real_name AS student_name FROM student_admin_service s " \
                  "LEFT JOIN sys_user u ON u.id=s.student_id WHERE s.service_type='请假'"
            params = []
            student = _find_student(conn, text)
            if student:
                sql += " AND s.student_id=?"
                params.append(student["id"])
            if "待审批" in text:
                sql += " AND s.status='待审批'"
            sql += " ORDER BY s.id DESC LIMIT 20"
            rows = rows_to_dicts(conn.execute(sql, params).fetchall())
            return _ok("查请假", sql, params, rows,
                       f"共{len(rows)}条请假记录。" if rows else "未找到请假记录。")

    return _miss("未识别", f"未识别到有效指令。支持：{SUPPORTED}。")