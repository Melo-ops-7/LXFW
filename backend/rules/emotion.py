"""心理情绪评估规则（FR-009，需求 9.2）。

- LLM 提供情绪标签/分值时优先采用；
- 否则关键词兜底：高危 90 / 负面 55 / 积极 15 / 默认平稳 20；
- 阈值：>=70 高危（写预警+通知班主任）；40-69 关注；<40 正常。
"""
import re

HIGH_RISK_KEYWORDS = [
    "自杀", "想死", "活不下去", "不想活", "轻生", "自残", "割腕",
    "跳楼", "活着没意思", "结束生命", "了结自己", "不想活了",
]
NEGATIVE_KEYWORDS = [
    "焦虑", "抑郁", "失眠", "压力好大", "压力大", "崩溃", "撑不住",
    "孤独", "想家", "难受", "烦躁", "想哭", "低落", "绝望", "疲惫",
    "跟不上", "挂科", "害怕", "迷茫",
]
POSITIVE_KEYWORDS = [
    "开心", "快乐", "顺利", "充实", "感恩", "兴奋", "期待", "高兴",
    "满足", "进步", "喜欢", "适应",
]

# 隐晦/隐喻式高危表达（正则兜底，Dify 不可用时仍能拦截；在线时由 LLM 风险评估节点兜底）
IMPLICIT_HIGH_RISK_PATTERNS = [
    (r"从?\s*\d+\s*楼.{0,10}(飞|跳|下去|坠|落)", "疑似跳楼（隐喻表达）"),
    (r"(飞|跳)到?\s*\d+\s*楼", "疑似跳楼（隐喻表达）"),
    (r"(喝|吞|服|吃).{0,8}(硫酸|盐酸|农药|百草枯|毒药|老鼠药|氰化物|敌敌畏)", "疑似服毒"),
    (r"煤气.{0,12}(睡|关窗|自杀|走了)", "疑似煤气中毒"),
    (r"关(上|好)?窗.{0,12}煤气", "疑似煤气中毒"),
    (r"烧炭.{0,8}(睡|取暖|自杀|关窗)", "疑似烧炭自杀"),
    (r"(整瓶|一瓶|全部|大量|一把).{0,8}(安眠药|药片|药).{0,8}(吞|吃|服|下去)", "疑似过量服药"),
    (r"(吞|吃|服).{0,6}(整瓶|一瓶|全部|大量|一把).{0,6}(安眠药|药片|药)", "疑似过量服药"),
    (r"(跳桥|跳河|跳江|跳海|卧轨|冲向车流|走向车流|撞车死)", "疑似轻生行为"),
    (r"(割|划).{0,4}(手腕|动脉)", "疑似自残"),
    (r"(一了百了|彻底解脱|永远睡过去|再也不想醒来|离开这个世界)", "疑似轻生意念（隐喻）"),
]


def evaluate(text: str, llm_tag: str = None, llm_score=None) -> dict:
    """返回 emotion_tag / emotion_score / risk_level / alerted / hit_keywords。

    安全优先：显式高危关键词与隐晦高危正则命中时，即使 LLM 给了低分也强制高危。
    """
    text = text or ""
    hit = []
    for kw in HIGH_RISK_KEYWORDS:
        if kw in text:
            hit.append(kw)
    if hit:
        return _result("高危", 90, hit)

    for pat, label in IMPLICIT_HIGH_RISK_PATTERNS:
        if re.search(pat, text):
            hit.append(label)
    if hit:
        return _result("高危", 90, list(dict.fromkeys(hit)))

    if llm_score is not None:
        try:
            score = max(0, min(100, int(llm_score)))
        except (TypeError, ValueError):
            score = None
        if score is not None:
            tag = llm_tag or ("高危" if score >= 70 else "负面" if score >= 40 else "平稳")
            return _result(tag, score, hit)

    for kw in NEGATIVE_KEYWORDS:
        if kw in text:
            hit.append(kw)
    if hit:
        return _result("负面", 55, hit)

    for kw in POSITIVE_KEYWORDS:
        if kw in text:
            hit.append(kw)
    if hit:
        return _result("积极", 15, hit)

    return _result(llm_tag or "平稳", 20, hit)


def _result(tag, score, hit):
    if score >= 70:
        risk, alerted = "高", True
    elif score >= 40:
        risk, alerted = "中", False
    else:
        risk, alerted = "低", False
    return {"emotion_tag": tag, "emotion_score": score, "risk_level": risk,
            "alerted": alerted, "hit_keywords": hit}