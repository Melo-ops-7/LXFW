# API 接口文档

Base URL：`http://localhost:8010`　交互式文档：`/docs`（Swagger）　OpenAPI：`/openapi.json`

## 鉴权约定

| 调用方 | 方式 |
|---|---|
| 前端登录用户 | `Authorization: Bearer <token>`（POST /api/auth/login 获取，24h 有效） |
| Dify 工具调用 | `X-API-Key: xinxifang-tool-key-2026`（backend/.env 的 TOOL_API_KEY） |
| 官网访客 | 客服对话/报名/留资/课程活动查询可匿名 |

错误码：400 参数非法 / 401 未登录或Key错误 / 403 角色越权 / 404 资源不存在 / 422 请求体校验失败 / 500 隐藏内部错误的统一提示。

## 1. 系统公共

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/health | 健康检查 → `{"status":"ok"}` |

## 2. 认证

| 方法 | 路径 | 入参 | 说明 |
|---|---|---|---|
| POST | /api/auth/login | username, password | → token + user（不含密码哈希） |
| GET | /api/auth/me | - | 当前登录用户 |

## 3. 画像研判（共享工具）

| 方法 | 路径 | 入参 | 说明 |
|---|---|---|---|
| POST | /api/profile/analyze | raw_text, name?, age?, education?, intent?, language?, hands_on?, budget?, llm_profile? | LLM字段优先+正则兜底 → profile / matches[{project,reason,score,detail}] / best_match / summary / message |

## 4. 学生侧

| 方法 | 路径 | 入参 | 说明 |
|---|---|---|---|
| POST | /api/student/leave | student_id, service_type?, start_time?, end_time?, reason | 未传时间从事由兜底解析；初始「待审批」；返回 time_parsed |
| GET | /api/student/leaves | student_id?, status? | 学生强制本人 |
| POST | /api/student/leave/approve | leave_id, approver_id?, approved, comment? | 仅班主任/管理员；不存在404 |
| POST | /api/student/emotion | student_id, text, emotion_tag?, emotion_score? | 评估+画像upsert+≥70写预警通知班主任 → emotion_tag/score/risk_level/alerted/alert_id/message |
| GET | /api/student/psych-profile | student_id | 画像（历史JSON已解析）；**仅班主任/管理员**，学生本人403 |
| POST | /api/student/mood | student_id, mood(1很好/2还不错/3一般/4很低落) | 今日心情打卡（同日可改）；连续3天最差→关注级(中)、连续5天→高危(高)写预警通知班主任，同一连续段不重复、关注可升高危 → streak/risk_level/watch/alerted/alert_id/message |
| GET | /api/student/mood | student_id? | 今日心情+近14天记录+当前连续天数（学生强制本人） |
| GET | /api/student/alerts | status?, student_id? | 仅班主任/管理员 |
| POST | /api/student/alerts/{id}/status | status(未处理/跟进中/已解除), teacher_id? | 更新预警状态 |
| POST | /api/student/feedback | student_id, content, detail? | 工单「待处理」 |
| GET | /api/student/feedbacks | student_id?, status? | 学生强制本人 |
| POST | /api/student/feedback/{id}/resolve | solution | 仅班主任/管理员；置「已解决」+is_notified=1 |
| GET | /api/student/scores | student_id?, course_name? | 学生强制本人 |
| GET | /api/student/overview | student_id | 请假+成绩+工单一次取回（Dify记录查询分支用）；心理画像字段仅员工可见，学生返回null |

## 5. 员工侧

| 方法 | 路径 | 入参 | 说明 |
|---|---|---|---|
| POST | /api/employee/leads | customer_name, contact_info?, background_info?, follow_up_history?, owner_employee_id? | 初始「新增意向」 |
| GET | /api/employee/leads | status?, owner_employee_id?, keyword? | 关键词模糊匹配姓名/背景 |
| GET | /api/employee/leads/{id} | - | 详情（跟进历史已解析）；不存在404 |
| PUT | /api/employee/leads/{id} | contact_info?, background_info?, follow_up_history? | 更新字段 |
| POST | /api/employee/leads/{id}/status | status | 仅四状态，非法400 |
| POST | /api/employee/reports | employee_id?, report_date?, content | 默认当天 |
| GET | /api/employee/reports | employee_id?, report_date? | 日报列表 |
| POST | /api/employee/scores | student_id, course_name, score, semester? | 学生不存在404 |
| GET | /api/employee/scores | student_id?, course_name? | 成绩查询 |
| GET | /api/employee/students | - | 学生名单（录入成绩选择用） |
| POST | /api/employee/nl2sql | text, employee_id? | → intent / sql / results / message；支持查成绩/录成绩/查日报/写日报/查客户/录客户/更新客户状态/查投诉/更新投诉状态/审批请假/查请假 |

## 6. 客服与活动（可匿名）

| 方法 | 路径 | 入参 | 说明 |
|---|---|---|---|
| GET | /api/courses | keyword?, category? | 项目列表 |
| GET | /api/courses/{id} | - | 项目详情 |
| POST | /api/courses/recommend | 同画像研判 | 推荐+项目关键信息+留资引导 |
| GET | /api/events | event_type? | 活动列表（含 remaining/is_full） |
| GET | /api/events/{id} | - | 活动详情 |
| POST | /api/events/register | event_id? 或 event_name?, customer_id?, customer_name?, contact_info? | 名额满400；活动不存在404；成功人数+1；访客自动创建CRM线索；防重复报名 |
| GET | /api/events/registrations | event_id? | 报名记录（含活动名/客户名） |
| GET | /api/faq | - | FAQ列表（与Dify知识库同源） |
| POST | /api/leads/public | customer_name, contact_info?, background_info? | 官网留资 |

## 7. 对话代理（前端 → 后端 → Dify）

| 方法 | 路径 | 入参 | 说明 |
|---|---|---|---|
| POST | /api/chat/{agent} | message, session_key?(访客) | agent=student/employee/service；自动续接conversation_id；学生/员工需登录；返回 reply/conversation_id/degraded/meta |
| GET | /api/chat/history | agent_type, limit?, session_key? | 本人对话历史 |
| POST | /api/chat/reset | agent_type, session_key? | 重置上下文 |

## 8. 管理后台（仅管理员）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /api/admin/overview | 客户/成绩/预警/工单/对话全域统计 |
| GET | /api/admin/users | 用户列表（user_type? 过滤） |
| POST | /api/admin/users | 新增用户（员工角色必须为顾问/班主任/管理员） |
| POST | /api/admin/users/{id}/status | 启用/禁用 |
| GET | /api/admin/conversations | 对话记录（agent_type?, limit?） |
| GET | /api/admin/system | 后端/数据库/Dify集成状态（不暴露密钥） |