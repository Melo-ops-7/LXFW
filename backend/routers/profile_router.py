"""画像研判路由（共享工具，FR-001~005 / FR-024）。"""
from fastapi import APIRouter

import schemas
from database import db, rows_to_dicts
from rules import profile as profile_rules

router = APIRouter(prefix="/api/profile", tags=["画像研判"])


@router.post("/analyze", summary="用户画像研判与项目推荐")
def analyze(body: schemas.ProfileIn):
    structured = {k: getattr(body, k) for k in
                  ("name", "age", "education", "intent", "language", "hands_on", "budget")}
    result = profile_rules.analyze(body.raw_text, body.llm_profile, structured)
    # 附带项目关键信息（学费/学制/适合人群，来自课程项目表，不编造）
    if result["matches"]:
        with db() as conn:
            names = [m["project"] for m in result["matches"]]
            placeholders = ",".join("?" * len(names))
            rows = rows_to_dicts(conn.execute(
                f"SELECT project_name,category,description,target_audience FROM course_project "
                f"WHERE project_name IN ({placeholders})", names).fetchall())
        info = {r["project_name"]: r for r in rows}
        for m in result["matches"]:
            m["detail"] = info.get(m["project"])
    return result