"""全局配置：从环境变量 / .env 读取，密钥不暴露给前端。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _load_dotenv():
    """轻量 .env 加载（不覆盖已存在的环境变量）。"""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# 数据库文件
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "xinxifang.db"))

# Dify 工具调用鉴权 Key（Dify HTTP 节点请求头 X-API-Key 携带）
TOOL_API_KEY = os.environ.get("TOOL_API_KEY", "xinxifang-tool-key-2026")

# Dify 服务地址与三个 Agent 应用的 API Key（在 Dify 应用「访问 API」页面生成）
DIFY_BASE_URL = os.environ.get("DIFY_BASE_URL", "http://localhost/v1")
DIFY_API_KEYS = {
    "student": os.environ.get("DIFY_STUDENT_API_KEY", ""),
    "employee": os.environ.get("DIFY_EMPLOYEE_API_KEY", ""),
    "service": os.environ.get("DIFY_SERVICE_API_KEY", ""),
}

# 登录令牌有效期（秒），演示级内存令牌
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "86400"))

# 心理预警阈值（需求 9.2）
ALERT_HIGH_THRESHOLD = 70
ALERT_WATCH_THRESHOLD = 40

# 情绪历史保留条数（需求 FR-010）
EMOTION_HISTORY_LIMIT = 50

# 知识库 FAQ 兜底文件（Dify 不可用时降级检索）
FAQ_JSON = PROJECT_ROOT / "knowledge" / "faq.json"