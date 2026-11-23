"""种子数据：账号、留学项目（来自甲方资料）、活动、示例客户/成绩/请假/工单。"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == digest


def run(conn):
    now = datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S"

    # ---------- 1. 统一用户（演示账号，密码见 README） ----------
    users = [
        # username, password, real_name, user_type, employee_role, department, contact
        ("admin", "admin123", "系统管理员", "EMPLOYEE", "管理员", "信息技术部", "020-8888 6666"),
        ("consultant1", "123456", "陈顾问", "EMPLOYEE", "顾问", "双元制事业部", "13800000001"),
        ("consultant2", "123456", "林顾问", "EMPLOYEE", "顾问", "研学服务事业部", "13800000002"),
        ("teacher1", "123456", "王班主任", "EMPLOYEE", "班主任", "学生服务部", "13800000003"),
        ("teacher2", "123456", "刘班主任", "EMPLOYEE", "班主任", "学生服务部", "13800000004"),
        ("student1", "123456", "张三", "STUDENT", None, "新加坡国际班", "1348907728"),
        ("student2", "123456", "李四", "STUDENT", None, "新加坡国际班", "13800000006"),
        ("student3", "123456", "许同学", "STUDENT", None, "德国双元制班", "13800000007"),
    ]
    for u in users:
        conn.execute(
            "INSERT INTO sys_user(username,password_hash,real_name,user_type,employee_role,department,contact_info) "
            "VALUES(?,?,?,?,?,?,?)",
            (u[0], hash_password(u[1]), u[2], u[3], u[4], u[5], u[6]),
        )

    # ---------- 2. 课程与项目（关键信息严格来自甲方资料） ----------
    projects = [
        ("2+2新加坡定向培养本科班", "新加坡升学",
         "国内前两年在培养基地学习新加坡国际课程结合的综合课程（第一年即可收到新加坡学院录取通知书）；第三年赴新加坡公费0学费留学（酒店运营6个月理论+6个月带薪实习，航空运营9个月理论+6个月带薪实习，其他专业12个月理论课程）；第四年直升本科课程并毕业，获世界综合排名200-500名左右大学颁发的毕业证书。四年学费总计约30-31万人民币：第一年（国内）学费75000元+学籍管理费50000元，第二年（国内）学费75000元，第三年（新加坡）0元，第四年计算机专业约19500新币（约11万元人民币）、其他专业约16500新币（约10万元人民币）。学历回国受中国教育部认证，享受留学生归国福利。",
         "应往届初中毕业生（约14-16岁）"),
        ("2+2+1本硕连读", "新加坡升学",
         "初中毕业经由2+2学制本科毕业后可直升硕士，最快1年制硕士毕业；可申请新加坡、中国香港、中国澳门、中国内地、英美澳加等TOP200名校硕士；是升入世界名校的安全、快捷且有保证的捷径。费用参考2+2国际本科班（四年约30-31万人民币）+硕士阶段费用。",
         "应往届初中毕业生（约14-16岁）"),
        ("0.5/1+2新加坡定向培养本科班", "新加坡升学",
         "第一年在国内参加0.5/1年预科课程（第一年即可收到新加坡学院录取通知书）；第二年前往新加坡公费0学费留学（酒店运营6个月理论+6个月带薪实习，航空运营9个月理论+6个月带薪实习，其他专业12个月理论课程）；第三年直升新加坡本科课程并毕业，获世界综合排名200-500名左右大学颁发的毕业证书。2.5/3年学费总计约25万-26万元人民币：第一年（国内）学费100000元/年+新加坡学籍费用50000元，第二年（新加坡）0元，第三年计算机专业约19500新币（约11万元人民币）、其他专业约16500新币（约10万元人民币）。学历回国受中国教育部认证，享受留学生归国福利；如选择在新加坡就业，受新加坡劳动法保护，就业薪资高达每月15000元人民币以上。",
         "高二在读、应往届高中毕业或中职中技同等学历毕业生（约16-19岁）"),
        ("0.5/1+2+1本硕连读", "新加坡升学",
         "高中毕业经由0.5/1+2学制本科毕业后可直升硕士，最快一年制硕士毕业；可申请新加坡、中国香港、中国澳门、中国内地、英美澳加等TOP200名校硕士；是升入世界名校的安全、快捷且有保证的捷径。费用参考0.5/1+2国际本科班（约25-26万人民币）+硕士阶段费用。",
         "高二在读、应往届高中毕业或中职中技同等学历毕业生（约16-19岁）"),
        ("6+6酒店运营大专就业班", "新加坡就业",
         "新加坡一带一路工学交替项目：6个月理论知识学习课程提升学术能力，6个月带薪实习积累工作经验，实习薪资6000-8000元人民币/月，一年即可获得大专文凭，实习结束100%推荐就业，就业薪资可达15000元人民币/月以上。无语言要求，节省大量时间，提升综合能力、英语水平与学历水平，解决就业问题。",
         "职高、中专、中职、技校学生，年龄满17岁，全国范围招生"),
        ("9+6航空运营大专就业班", "新加坡就业",
         "新加坡一带一路工学交替项目：9个月理论知识学习课程+6个月带薪实习，实习薪资6000-8000元人民币/月，一年即可获得大专文凭，实习结束100%推荐就业，就业薪资可达15000元人民币/月以上。无语言要求，年满17周岁即可轻松申请，全方位提升综合素质与英语能力，从根本上解决就业难题。",
         "职高、中专、中职、技校学生，年满17周岁，全国范围招生"),
        ("一年制专升本", "新加坡升学",
         "国内专科升本科一般需2-3年，同等条件下就读国外名校专升本只需1-1.5年，录取世界名校实现弯道超车。学历回国受中国教育部认证，享受留学生归国福利。",
         "国内专科毕业生"),
        ("一年制本升硕", "新加坡升学",
         "国内本科升研究生一般需2-3年，同等条件下就读国外名校本科升硕士仅需一年，录取世界名校实现弯道超车。学历回国受中国教育部认证，享受留学生归国福利。",
         "国内本科毕业生"),
        ("德国双元制精英人才共建计划", "德国双元制",
         "德国职业人才培养计划：职业学校学习专业知识+企业实训职业技能，培训年限2-3.5年。三大优势：省属教育国企直接签协议、银行全额低息贷款、国内外全程保姆式服务。免学费、无学籍注册费；培训期间享津贴（机电一体化专业第一年880欧/月、第二年950欧/月、第三年1030欧/月，3年共34320欧约合人民币275000元）；完成培训考取IHK/HWK职业资格证书后可与实习企业签订正式劳动合同，平均薪资2100-3500欧/月；可升学（申请德国大学免德福、免APS审核）；工作两年后可申请德国永居。专业类别：医疗健康类、机械制造类、商贸会计类、电子电器类、汽车服务类、酒店管理类。国内需线下封闭式实训6-12个月通过德语欧标B1后匹配德国企业面试。",
         "18-35岁，高中及以上学历，动手能力强、逻辑思维强、无犯罪记录，有一定德语学习能力和表达能力"),
    ]
    conn.executemany(
        "INSERT INTO course_project(project_name,category,description,target_audience) VALUES(?,?,?,?)",
        projects,
    )

    # ---------- 3. 活动与讲座（含一个已满活动用于验收 ACC-004） ----------
    events = [
        ("新加坡留学分享会", "线下", (now + timedelta(days=7)).strftime(fmt),
         "广州市越秀区五山路200号新西方教育大厦三楼", 50, 12),
        ("新加坡项目招生官见面会", "线上", (now + timedelta(days=10)).strftime(fmt),
         "腾讯会议（报名后发送链接）", 100, 35),
        ("德国双元制项目说明会", "线下", (now + timedelta(days=14)).strftime(fmt),
         "广州市越秀区五山路200号新西方教育大厦三楼", 30, 8),
        ("留学政策线上讲座（满员测试场）", "线上", (now + timedelta(days=3)).strftime(fmt),
         "腾讯会议（报名后发送链接）", 2, 2),
    ]
    conn.executemany(
        "INSERT INTO event_lecture(event_name,event_type,start_time,location,max_participants,current_participants) "
        "VALUES(?,?,?,?,?,?)", events,
    )

    # ---------- 4. 意向客户（含验收用例「许同学」） ----------
    leads = [
        ("许同学", "13800000007", "19岁，高中刚毕业，想快点拿本科学历，家庭预算中等，意向新加坡升学",
         json.dumps([
             {"time": (now - timedelta(days=6)).strftime(fmt), "by": "陈顾问", "note": "首次电话沟通，介绍0.5/1+2项目"},
             {"time": (now - timedelta(days=3)).strftime(fmt), "by": "陈顾问", "note": "发送项目资料与学费明细，家长表示考虑"},
             {"time": (now - timedelta(days=1)).strftime(fmt), "by": "陈顾问", "note": "邀约参加新加坡留学分享会"},
         ], ensure_ascii=False), "跟进中", 2),
        ("张三家长", "1348907728", "孩子张三19岁高中毕业，家里经济条件好，已签约新加坡国际班",
         json.dumps([{"time": (now - timedelta(days=20)).strftime(fmt), "by": "陈顾问", "note": "签约0.5/1+2本科班"}],
                    ensure_ascii=False), "已签约", 2),
        ("刘女士", "13900000009", "孩子中职技校毕业17岁，想尽快就业，关注6+6酒店运营大专就业班",
         json.dumps([{"time": (now - timedelta(days=2)).strftime(fmt), "by": "林顾问", "note": "微信咨询就业班薪资与实习安排"}],
                    ensure_ascii=False), "新增意向", 3),
        ("周先生", "13900000010", "28岁本科毕业，有德语B1基础，动手能力强，意向德国双元制+移民",
         json.dumps([], ensure_ascii=False), "新增意向", 2),
    ]
    conn.executemany(
        "INSERT INTO crm_lead(customer_name,contact_info,background_info,follow_up_history,status,owner_employee_id) "
        "VALUES(?,?,?,?,?,?)", leads,
    )

    # ---------- 5. 学生成绩 ----------
    scores = [
        (6, "英语（预科）", 88.5, "2026秋季"),
        (6, "新加坡国际课程导论", 92.0, "2026秋季"),
        (6, "心理测评", 85.0, "2026秋季"),
        (7, "英语（预科）", 79.0, "2026秋季"),
        (7, "计算机基础", 90.5, "2026秋季"),
        (8, "德语B1强化", 82.0, "2026秋季"),
        (8, "机械制图实训", 91.0, "2026秋季"),
    ]
    conn.executemany(
        "INSERT INTO student_score(student_id,course_name,score,semester) VALUES(?,?,?,?)", scores,
    )

    # ---------- 6. 示例请假 / 工单 / 心理画像 ----------
    conn.execute(
        "INSERT INTO student_admin_service(student_id,service_type,start_time,end_time,reason,status) "
        "VALUES(?,?,?,?,?,?)",
        (6, "请假", (now - timedelta(days=2)).strftime(fmt), (now - timedelta(days=1)).strftime(fmt),
         "家里有事", "已通过"),
    )
    conn.execute("UPDATE student_admin_service SET approver_id=4 WHERE student_id=6")
    conn.execute(
        "INSERT INTO student_feedback_ticket(student_id,content,detail,status) VALUES(?,?,?,?)",
        (7, "宿舍空调维修慢", "报修三天仍未处理，希望加快进度", "待处理"),
    )
    conn.execute(
        "INSERT INTO student_psych_profile(student_id,latest_emotion_tag,emotion_score,last_interaction_time,emotion_history) "
        "VALUES(?,?,?,?,?)",
        (6, "平稳", 20, now.strftime(fmt),
         json.dumps([{"time": now.strftime(fmt), "tag": "平稳", "score": 20}], ensure_ascii=False)),
    )

    # ---------- 7. 示例日报 ----------
    conn.execute(
        "INSERT INTO employee_daily_report(employee_id,report_date,content) VALUES(?,?,?)",
        (2, now.strftime("%Y-%m-%d"), "跟进许同学家长，发送0.5/1+2项目学费明细；邀约留学分享会；新增线索1条。"),
    )