-- ============================================================
-- 新西方留学服务智能教育服务助手系统 - SQLite 建表脚本（12 张表）
-- 契约来源：《sql设计草稿.txt》+ 需求规格说明书 14.1 核心数据对象
-- 首次启动由 backend/database.py 自动执行并写入种子数据
-- ============================================================

-- 1. 统一用户表
CREATE TABLE IF NOT EXISTS sys_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,          -- 用户名/登录账号
    password_hash TEXT NOT NULL,            -- 加密后的密码（sha256+salt）
    real_name TEXT NOT NULL,                -- 真实姓名
    user_type TEXT NOT NULL,                -- 用户大类（STUDENT 学生 / EMPLOYEE 员工）
    employee_role TEXT,                     -- 员工角色（顾问 / 班主任 / 管理员）
    department TEXT,                        -- 所属部门/院系
    contact_info TEXT,                      -- 联系方式（手机号/邮箱）
    status TEXT DEFAULT '正常',             -- 账号状态（正常/禁用）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. 学生行政服务表（请假、考务等申请）
CREATE TABLE IF NOT EXISTS student_admin_service (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    service_type TEXT NOT NULL,             -- 服务类型（请假/考务查询）
    start_time DATETIME,
    end_time DATETIME,
    reason TEXT,
    status TEXT DEFAULT '待审批',           -- 待审批/已通过/已驳回
    approver_id INTEGER,
    related_academic_id INTEGER,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. 心理健康画像表（每名学生唯一，upsert 维护）
CREATE TABLE IF NOT EXISTS student_psych_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE,
    latest_emotion_tag TEXT,
    emotion_score INTEGER,
    last_interaction_time DATETIME,
    emotion_history TEXT,                   -- JSON 数组，仅保留最近 50 条
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. 心理预警表
CREATE TABLE IF NOT EXISTS student_psych_alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    trigger_reason TEXT NOT NULL,
    risk_level TEXT NOT NULL,               -- 高/中/低
    status TEXT DEFAULT '未处理',           -- 未处理/跟进中/已解除
    teacher_id INTEGER,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4.1 心情打卡表（学生每日心情反馈，连续3天最差心情→关注级，连续5天→高危预警）
CREATE TABLE IF NOT EXISTS student_mood (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    mood_date TEXT NOT NULL,                -- YYYY-MM-DD
    mood INTEGER NOT NULL,                  -- 1很好 2还不错 3一般 4很低落(最差)
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, mood_date)
);

-- 5. 售后反馈工单表
CREATE TABLE IF NOT EXISTS student_feedback_ticket (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    detail TEXT,
    status TEXT DEFAULT '待处理',           -- 待处理/处理中/已解决
    solution TEXT,
    is_notified INTEGER DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. 意向客户表（CRM）
CREATE TABLE IF NOT EXISTS crm_lead (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    contact_info TEXT,
    background_info TEXT,
    follow_up_history TEXT,
    status TEXT DEFAULT '新增意向',         -- 新增意向/跟进中/已签约/已流失
    owner_employee_id INTEGER NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 7. 员工日报表
CREATE TABLE IF NOT EXISTS employee_daily_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    content TEXT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 8. 学生成绩表
CREATE TABLE IF NOT EXISTS student_score (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_name TEXT NOT NULL,
    score REAL NOT NULL,
    semester TEXT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 9. 课程与项目表
CREATE TABLE IF NOT EXISTS course_project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    target_audience TEXT
);

-- 10. 活动与讲座表
CREATE TABLE IF NOT EXISTS event_lecture (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    event_type TEXT,                        -- 线上/线下
    start_time DATETIME NOT NULL,
    location TEXT,
    max_participants INTEGER,
    current_participants INTEGER DEFAULT 0
);

-- 11. 活动报名表
CREATE TABLE IF NOT EXISTS event_registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    status TEXT DEFAULT '已报名',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES event_lecture(id)
);

-- 12. 对话记录表（沉淀各 Agent 对话；扩展 dify 会话字段用于上下文续接）
CREATE TABLE IF NOT EXISTS conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,                  -- 用户ID（学生/员工ID 或访客 session_key）
    agent_type TEXT NOT NULL,               -- student / employee / service
    user_input TEXT NOT NULL,
    ai_reply TEXT,
    emotion_tag TEXT,
    dify_conversation_id TEXT,              -- Dify 会话ID（上下文续接）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_admin_student ON student_admin_service(student_id);
CREATE INDEX IF NOT EXISTS idx_alert_student ON student_psych_alert(student_id);
CREATE INDEX IF NOT EXISTS idx_feedback_student ON student_feedback_ticket(student_id);
CREATE INDEX IF NOT EXISTS idx_score_student ON student_score(student_id);
CREATE INDEX IF NOT EXISTS idx_lead_owner ON crm_lead(owner_employee_id);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversation_log(user_id, agent_type);

-- 13. 登录令牌表（持久化会话：后端重启不掉线，同一账号多端并行登录互不影响）
CREATE TABLE IF NOT EXISTS sys_token (
    token TEXT PRIMARY KEY,
    user_json TEXT NOT NULL,                -- 登录用户信息快照（JSON）
    expire REAL NOT NULL                    -- 过期时间戳（秒）
);
CREATE INDEX IF NOT EXISTS idx_token_expire ON sys_token(expire);