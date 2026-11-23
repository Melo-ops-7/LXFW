# Dify 接入指南

本系统采用「Dify 编排层（大脑）+ FastAPI 后端（手脚）」架构。Dify 负责意图分类、知识库 RAG、
LLM 话术组织；后端负责规则计算与数据读写。两者通过 HTTP API 桥接。

> 前提：后端已启动（默认 `http://localhost:8010`），Dify 已部署并接入 LLM 插件。

---

## 第一步：创建知识库（4 个）

在 Dify「知识库」中创建以下 4 个知识库，文件均在项目 `knowledge/` 目录：

| 知识库 | 上传文件 | 分段方式 |
|---|---|---|
| 公司信息 | `01_公司信息.md`、`06_新人指南.md` | 自动分段 |
| 留学政策 | `02_留学政策_新加坡.md`、`03_留学政策_德国.md` | 自动分段（政策类可稍大） |
| 业务项目 | `04_业务项目_新加坡.md`、`05_业务项目_德国双元制.md`、`07_用户画像研判规则.md` | 自动分段 |
| 常见问答FAQ | `faq.csv` | **Q&A 分段模式**（问答对最佳实践，秒回） |

分段参数建议：
- 分段长度（chunk size）：500 左右，政策类可调到 800
- 分段重叠（overlap）：50 左右
- **Embedding 模型：选中文友好的模型（推荐 bge-m3 / m3e / text2vec）**，中文检索质量几乎完全取决于它
- 检索设置：topK = 4~5，score 阈值 0.4（DSL 中已按此配置），可选 Rerank 精排

> `knowledge/原始资料/` 为甲方原始文件备份。面试/简历类个人资料不建议上传知识库。

## 第二步：导入 3 个 Agent 应用

Dify「工作室 → 导入 DSL 文件」，依次导入 `dify/` 下三个文件（均为 Chatflow / advanced-chat）：

| 文件 | 应用 | 意图分支 |
|---|---|---|
| `student_agent.yml` | 留学生智能管家 | 请假 / 记录查询 / 售后反馈 / 情绪关怀 / 升学咨询 / 其他 |
| `employee_agent.yml` | 员工业务助手 | 客户管理 / 日报 / 成绩 / 请假审批 / 投诉工单 / 新人指南 / 其他 |
| `service_agent.yml` | 客服与活动 | 政策费用咨询 / FAQ / 项目推荐 / 活动查询 / 活动报名 / 闲聊 |

## 第三步：导入后必做的 3 项配置

1. **选择模型**：DSL 中模型占位为 `qwen-plus（tongyi）`。打开每个「意图分类」和「LLM」节点，
   改为你已接入的 LLM 插件模型（分类/抽取节点建议 temperature 0~0.1，话术节点 0.3~0.6）。
2. **绑定知识库**：打开每个「知识库检索」节点，勾选第一步创建的知识库：
   - 学生管家 → 公司信息 + 留学政策 + 业务项目 + FAQ
   - 员工助手 → 公司信息（含新人指南）
   - 客服 → 全部 4 个
3. **核对后端地址**：HTTP 节点 URL 默认 `http://host.docker.internal:8010`
   （Docker 版 Dify 访问宿主机）。若 Dify 与后端同机非 Docker 部署，改为 `http://127.0.0.1:8010`；
   若后端在其他机器，改为对应 IP。请求头 `X-API-Key: xinxifang-tool-key-2026` 已内置，
   与 `backend/.env` 的 `TOOL_API_KEY` 保持一致即可。

> 自由文本（请假事由、投诉内容等）均先经 Python 代码节点 `json.dumps` 构造请求体，
> 避免引号/换行破坏 JSON；LLM 画像抽取结果解析失败时后端自动正则兜底（FR-001）。

## 第四步：生成 API Key 并配置后端

每个应用「访问 API → API 服务器 → 生成密钥」，把 3 个 Key 填入 `backend/.env`
（复制 `.env.example` 为 `.env`）：

```env
TOOL_API_KEY=xinxifang-tool-key-2026
DIFY_BASE_URL=http://localhost/v1
DIFY_STUDENT_API_KEY=app-xxxxxxxx
DIFY_EMPLOYEE_API_KEY=app-xxxxxxxx
DIFY_SERVICE_API_KEY=app-xxxxxxxx
```

重启后端。前端聊天即走完整链路：

```
前端 → POST /api/chat/{agent}（后端代理，Key 不暴露给浏览器）
     → Dify /chat-messages（携带 conversation_id 续接上下文）
     → 意图分类 → 知识库检索 / HTTP 工具调后端 → LLM 话术 → 返回
     → 后端沉淀 conversation_log（含情绪标签）
```

未配置 Key 或 Dify 不可用时自动降级为本地规则应答（需求 11.1），系统不会整体不可用。

## 上下文与判断能力说明

- **会话续接**：后端按「用户 + Agent」保存 Dify `conversation_id`（conversation_log 表），
  同一用户多轮对话自动续接；前端「⟳」按钮或 `POST /api/chat/reset` 可重置。
- **记忆窗口**：所有对话型 LLM 节点开启 memory（window=10），分类器 instruction 要求结合历史判断，
  支持「那德国呢」「把他状态改为已签约」等指代。
- **身份注入**：后端把 `student_id / employee_id / employee_role / user_name` 作为 inputs 注入
  Dify 开始节点，工具调用据此定位数据，学生无法越权。

## 自定义工具（可选）

DSL 已用 HTTP 请求节点直连后端，无需额外配置工具。若想在 Dify「工具」中统一管理，
可导入 `dify/tools_openapi.json`（或直接使用运行中的 `http://localhost:8010/openapi.json`），
鉴权方式选 API Key → Custom Header `X-API-Key`。

## 直连 Dify 的跨域说明（本系统不需要）

本系统前端经后端代理调用 Dify，**无需修改 Dify nginx**。若未来要前端双击直连 Dify API，
按架构分析文档在 Dify nginx `location /v1` 增加 CORS 头并 `docker compose restart nginx`。

## 联调检查清单

- [ ] 后端 `GET /api/health` 返回 `{"status":"ok"}`
- [ ] Dify 中 HTTP 节点「运行此步骤」能拿到后端 JSON（检查 host.docker.internal 与端口）
- [ ] 客服问「新加坡2+2四年学费多少？」→ 回答 30-31 万（来自知识库，不编造）
- [ ] 客服输入「19岁高中毕业想拿本科」→ 推荐 0.5/1+2，匹配度 93 分
- [ ] 学生输入「最近压力好大，感觉活不下去了」→ 高危预警，班主任后台可见
- [ ] 学生输入「我明天要请假一天」→ 生成待审批记录，班主任可审批
- [ ] 员工输入「帮我查一下许同学的跟进记录」→ 返回客户档案
- [ ] 客户「报名留学分享会，张三，13800000000」→ 报名成功，人数+1
- [ ] 追问「那德国项目呢」→ 上下文正确续接