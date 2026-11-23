"""Pydantic 入参/出参模型（统一契约，字段 snake_case）。"""
import json
from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileIn(BaseModel):
    raw_text: str = ""
    name: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    intent: Optional[str] = None
    language: Optional[str] = None
    hands_on: Optional[bool] = None
    budget: Optional[str] = None
    llm_profile: Optional[dict] = None  # Dify LLM 抽取的结构化画像

    @model_validator(mode="before")
    @classmethod
    def _parse_llm_profile(cls, data):
        """Dify 自定义工具以字符串传画像 JSON，此处自动解析为 dict。"""
        if isinstance(data, dict) and isinstance(data.get("llm_profile"), str):
            try:
                data["llm_profile"] = json.loads(data["llm_profile"]) or None
            except Exception:
                data["llm_profile"] = None
        return data


class LeaveIn(BaseModel):
    student_id: int
    service_type: str = "请假"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: str = ""


class LeaveApproveIn(BaseModel):
    leave_id: int
    approver_id: Optional[int] = None
    approved: bool
    comment: Optional[str] = None


class EmotionIn(BaseModel):
    student_id: int
    text: str
    emotion_tag: Optional[str] = None
    emotion_score: Optional[int] = None


class AlertStatusIn(BaseModel):
    status: str = Field(pattern="^(未处理|跟进中|已解除)$")
    teacher_id: Optional[int] = None


class MoodIn(BaseModel):
    student_id: int
    mood: int = Field(ge=1, le=4)  # 1很好 2还不错 3一般 4很低落(最差)


class FeedbackIn(BaseModel):
    student_id: int
    content: str
    detail: Optional[str] = None


class FeedbackResolveIn(BaseModel):
    solution: str


class LeadIn(BaseModel):
    customer_name: str
    contact_info: Optional[str] = None
    background_info: Optional[str] = None
    follow_up_history: Optional[str] = None
    owner_employee_id: Optional[int] = None


class LeadUpdateIn(BaseModel):
    contact_info: Optional[str] = None
    background_info: Optional[str] = None
    follow_up_history: Optional[str] = None


class LeadStatusIn(BaseModel):
    status: str


class ReportIn(BaseModel):
    employee_id: Optional[int] = None
    report_date: Optional[str] = None
    content: str


class ScoreIn(BaseModel):
    student_id: int
    course_name: str
    score: float
    semester: Optional[str] = None


class NL2SQLIn(BaseModel):
    text: str
    employee_id: Optional[int] = None


class RegisterIn(BaseModel):
    event_id: Optional[int] = None
    event_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    contact_info: Optional[str] = None


class ChatIn(BaseModel):
    message: str
    session_key: Optional[str] = None  # 官网访客会话标识


class UserIn(BaseModel):
    username: str
    password: str
    real_name: str
    user_type: str = Field(pattern="^(STUDENT|EMPLOYEE)$")
    employee_role: Optional[str] = None
    department: Optional[str] = None
    contact_info: Optional[str] = None


class UserStatusIn(BaseModel):
    status: str = Field(pattern="^(正常|禁用)$")