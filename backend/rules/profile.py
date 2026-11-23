"""用户画像研判规则引擎（FR-001 ~ FR-005，需求 9.1）。

- 优先采用 LLM 抽取的结构化字段（llm_profile），未提供时用正则关键词兜底；
- 学历归一化优先级：硕士 → 本科 → 专科 → 中职技校 → 高中 → 初中；
- 学历抽取识别「X毕业 / X在读 / X刚毕业」语境，排除「想拿本科」等目标学历表述；
- 规则匹配确定性计算，无匹配时明确提示，不编造推荐。
"""
import re

# 标准学历桶（按优先级排序）
EDU_BUCKETS = [
    ("硕士", ["硕士", "研究生", "硕士生"]),
    ("本科", ["本科", "大学本科", "学士"]),
    ("专科", ["专科", "大专", "高职"]),
    ("中职技校", ["中职", "中技", "中专", "技校", "职高", "职业高中"]),
    ("高中", ["高中", "普高", "高二", "高三", "高一"]),
    ("初中", ["初中", "初级中学"]),
]

# 目标学历表述（不是当前学历，需先剔除）
_TARGET_PATTERNS = [
    r"(?:想|想要|希望|打算|准备|计划|期望|目标是?|打算要)[^，。,；;]{0,8}?(?:拿到?|获得|读|升|考取|申请|拿下)[^，。,；;]{0,4}?(?:本科|硕士|研究生|大专|学历|文凭)",
    r"专升本", r"本升硕", r"升本科", r"升硕士", r"拿本科", r"拿硕士", r"读本科", r"读硕士",
    r"(?:本科|硕士)(?:学历|文凭)?(?:提升|深造)",
]

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def normalize_education(text):
    """FR-002 学历归一化：按优先级匹配关键词，无法归一的原样返回。"""
    if not text:
        return None
    for bucket, keywords in EDU_BUCKETS:
        for kw in keywords:
            if kw in str(text):
                return bucket
    return str(text)


def normalize_intent(text):
    """FR-003 意向归一化：就业 / 移民 / 升学。"""
    if not text:
        return None
    t = str(text)
    if re.search(r"就业|工作|上班|求职", t):
        return "就业"
    if re.search(r"移民|永居|定居", t):
        return "移民"
    if re.search(r"升学|学历|本科|硕士|留学|深造|读书|上学", t):
        return "升学"
    return None


def _extract_age(text):
    m = re.search(r"(\d{1,2})\s*(?:岁|周岁)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"年龄[：:\s]*(\d{1,2})", text)
    if m:
        return int(m.group(1))
    return None


def _extract_education(text):
    """FR-001 语境抽取：先剔除目标学历表述，再匹配「X毕业/在读/刚毕业」。"""
    cleaned = text
    for pat in _TARGET_PATTERNS:
        cleaned = re.sub(pat, "", cleaned)
    # 带语境的学历表述优先
    ctx = re.search(
        r"(初中|高中|中职|中技|中专|技校|职高|专科|大专|本科|硕士|研究生)"
        r"(?:刚毕业|毕业|在读|结业|应届|往届|学历)", cleaned)
    if ctx:
        return normalize_education(ctx.group(1))
    # 退化为优先级关键词匹配
    for bucket, keywords in EDU_BUCKETS:
        for kw in keywords:
            if kw in cleaned:
                return bucket
    return None


def extract_profile(raw_text: str, llm_profile: dict = None, structured: dict = None) -> dict:
    """FR-001 画像抽取：LLM 结构化字段优先，正则兜底。"""
    raw_text = raw_text or ""
    profile = {"name": None, "age": None, "education": None, "intent": None,
               "language": None, "hands_on": None, "budget": None}

    # 1) 显式结构化字段（接口直传）
    if structured:
        for k in profile:
            if structured.get(k) not in (None, ""):
                profile[k] = structured[k]

    # 2) LLM 抽取字段（Dify 传入）
    if llm_profile:
        for k in profile:
            if profile[k] in (None, "") and llm_profile.get(k) not in (None, ""):
                profile[k] = llm_profile[k]

    # 3) 正则兜底
    if profile["age"] is None:
        profile["age"] = _extract_age(raw_text)
    if profile["education"] is None:
        profile["education"] = _extract_education(raw_text)
    if profile["intent"] is None:
        profile["intent"] = normalize_intent(raw_text)
    if profile["name"] is None:
        m = re.search(r"(?:姓名|名字)[：:\s]*([\u4e00-\u9fa5]{2,4})", raw_text)
        if m:
            profile["name"] = m.group(1)
    if profile["language"] is None:
        if re.search(r"德语|歌德|B1", raw_text):
            profile["language"] = "德语"
        elif re.search(r"英语|雅思|托福", raw_text):
            profile["language"] = "英语"
    if profile["hands_on"] is None:
        if re.search(r"动手能力(?:强|好|不错)|动手能力强|实操能力强|喜欢动手", raw_text):
            profile["hands_on"] = True
    if profile["budget"] is None:
        if re.search(r"很有钱|经济条件好|预算充足|家庭富裕", raw_text):
            profile["budget"] = "充足"
        elif re.search(r"预算有限|经济一般|费用敏感", raw_text):
            profile["budget"] = "有限"

    # 归一化
    if profile["education"]:
        profile["education"] = normalize_education(profile["education"])
    if profile["intent"]:
        profile["intent"] = normalize_intent(profile["intent"]) or profile["intent"]
    if profile["age"] is not None:
        try:
            profile["age"] = int(profile["age"])
        except (TypeError, ValueError):
            profile["age"] = None
    if isinstance(profile["hands_on"], str):
        profile["hands_on"] = profile["hands_on"] in ("true", "True", "是", "强", "好")
    return profile


# ---------- FR-004 规则匹配 ----------
# 项目基础分与类别（类别用于 FR-005 意向加分）
_BASE_PROJECTS = {
    "2+2新加坡定向培养本科班": (85, "升学"),
    "2+2+1本硕连读": (82, "升学"),
    "0.5/1+2新加坡定向培养本科班": (90, "升学"),
    "0.5/1+2+1本硕连读": (86, "升学"),
    "6+6酒店运营大专就业班": (85, "就业"),
    "9+6航空运营大专就业班": (85, "就业"),
    "一年制专升本": (90, "升学"),
    "一年制本升硕": (90, "升学"),
    "德国双元制精英人才共建计划": (82, "双元制"),
}

_EDU_POOL = {
    "初中": ["2+2新加坡定向培养本科班", "2+2+1本硕连读"],
    "高中": ["0.5/1+2新加坡定向培养本科班", "0.5/1+2+1本硕连读"],
    "中职技校": ["0.5/1+2新加坡定向培养本科班", "0.5/1+2+1本硕连读"],
    "专科": ["一年制专升本"],
    "本科": ["一年制本升硕"],
}


def _reason_for(project, profile, bonus, bonus_desc):
    """生成可解释的推荐理由。"""
    parts = []
    edu = profile.get("education")
    age = profile.get("age")
    if project.startswith("2+2"):
        parts.append("初中学历符合2+2学制招生要求（应往届初中毕业生）")
    elif project.startswith("0.5/1+2"):
        parts.append(f"{edu or '高中/中职'}学历符合招生要求（高二在读、应往届高中毕业或中职中技同等学历）")
    elif project.startswith(("6+6", "9+6")):
        parts.append("中职技校学历且年满17岁，符合就业班招生要求，无语言要求")
    elif project == "一年制专升本":
        parts.append("专科学历可1-1.5年快速升本，学历受中国教育部认证")
    elif project == "一年制本升硕":
        parts.append("本科学历可一年制升硕，学历受中国教育部认证")
    elif project.startswith("德国双元制"):
        parts.append("18-35岁、高中及以上学历、有德语基础且动手能力强，符合双元制报名要求")
    if age and project.startswith("0.5/1+2") and 16 <= age <= 19:
        parts.append(f"{age}岁处于16-19岁适龄区间")
    if age and project.startswith("2+2") and 14 <= age <= 16:
        parts.append(f"{age}岁处于14-16岁适龄区间")
    if bonus:
        parts.append(bonus_desc)
    return "；".join(parts) + "。"


def match_projects(profile: dict) -> dict:
    """FR-004/005：规则匹配 + 匹配度评分排序。返回 matches/best_match/summary/message。"""
    edu = profile.get("education")
    age = profile.get("age")
    intent = profile.get("intent")
    language = profile.get("language") or ""
    hands_on = profile.get("hands_on")

    if not edu:
        return {"matches": [], "best_match": None, "summary": "",
                "message": "画像信息不足：请补充学历信息（如初中/高中/中职/专科/本科），以便进行项目匹配。"}

    candidates = []  # (project, base_score, category)
    for name in _EDU_POOL.get(edu, []):
        base, cat = _BASE_PROJECTS[name]
        candidates.append((name, base, cat))

    # 就业导向：中职技校 + 年龄>=17
    if edu == "中职技校" and age is not None and age >= 17:
        for name in ("6+6酒店运营大专就业班", "9+6航空运营大专就业班"):
            base, cat = _BASE_PROJECTS[name]
            candidates.append((name, base, cat))

    # 德国双元制：18-35岁 + 高中及以上 + 德语基础 + 动手能力强
    if (age is not None and 18 <= age <= 35
            and edu in ("高中", "中职技校", "专科", "本科", "硕士")
            and "德语" in str(language) and hands_on):
        base, cat = _BASE_PROJECTS["德国双元制精英人才共建计划"]
        candidates.append(("德国双元制精英人才共建计划", base, cat))

    if not candidates:
        return {"matches": [], "best_match": None, "summary": "",
                "message": f"未匹配到合适项目：当前画像（学历：{edu}）暂无对应留学项目，建议联系人工顾问进一步评估。"}

    # FR-005 意向加分（上限100，去重）
    seen, matches = set(), []
    for name, base, cat in candidates:
        if name in seen:
            continue
        seen.add(name)
        bonus, bonus_desc = 0, ""
        if intent == "就业" and cat in ("就业", "双元制"):
            bonus, bonus_desc = 5, "就业意向与项目就业导向一致（+5分）"
        elif intent == "升学" and cat == "升学":
            bonus, bonus_desc = 3, "升学意向与本科/硕士培养目标一致（+3分）"
        elif intent == "移民" and cat == "双元制":
            bonus, bonus_desc = 5, "移民意向与德国永居通道一致（+5分）"
        score = min(100, base + bonus)
        matches.append({"project": name, "score": score,
                        "reason": _reason_for(name, profile, bonus, bonus_desc)})

    matches.sort(key=lambda m: m["score"], reverse=True)
    best = matches[0]
    who = profile.get("name") or "该用户"
    summary = (f"{who}（{edu}"
               + (f"，{age}岁" if age else "")
               + (f"，意向{intent}" if intent else "")
               + f"）推荐【{best['project']}】，匹配度{best['score']}分。{best['reason']}")
    return {"matches": matches, "best_match": best, "summary": summary, "message": None}


def analyze(raw_text: str = "", llm_profile: dict = None, structured: dict = None) -> dict:
    """画像研判入口：抽取 → 归一化 → 匹配 → 评分。"""
    profile = extract_profile(raw_text, llm_profile, structured)
    result = match_projects(profile)
    return {"profile": profile, **result}