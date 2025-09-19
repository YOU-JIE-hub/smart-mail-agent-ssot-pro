#!/usr/bin/env python3
import re
def classify_priority(text: str, fields: dict | None = None) -> dict:
    t = text.lower()
    fields = fields or {}
    env = set([e.lower() for e in fields.get("env", [])])
    http_err = set(fields.get("http_errors", []))

    kw_p1 = [
        r"服務.*中斷", r"無法登入", r"完全.*失敗", r"整體.*不可用", r"崩潰", r"災難",
        r"\boutage\b", r"\bsystem\s*down\b", r"\bcannot\s*log[\s\-]?in\b", r"\bcan't\s*log[\s\-]?in\b",
    ]
    kw_p2 = [
        r"變慢|延遲|不穩|卡|排程.*更動|久未處理|沒有實質?更新|沒有里程碑|請提供\s*eta",
        r"\blatenc(y|ies)\b|\bslow\b|\bdegrad", r"\brates?\s*limit|429",
    ]
    urgent = [r"\bASAP\b", r"今天|今日|今晚|立刻|盡快", r"\bEOD\b|\bEOW\b|\bETA\b"]

    def hit(pats): 
        return any(re.search(p, t, flags=re.I) for p in pats)

    # 強規則：prod + 500/大量失敗/關鍵字
    if ("prod" in env or "production" in env or "prod" in t) and (("500" in http_err) or re.search(r"\b500\b", t)):
        return {"priority":"P1", "reason":"prod+500"}

    if hit(kw_p1):
        if any(re.search(u, t, flags=re.I) for u in urgent):
            return {"priority":"P1", "reason":"outage+urgent"}
        # 非 urgent 也視為 P1
        return {"priority":"P1", "reason":"outage/critical"}

    # 中度：429、UAT/沙箱重大問題、長時間無更新/多次改期、效能劣化
    if "429" in http_err or re.search(r"\b429\b", t):
        return {"priority":"P2", "reason":"rate_limit_429"}
    if "uat" in env or "sandbox" in env or re.search(r"\buat\b|sandbox", t, flags=re.I):
        if hit(kw_p2):
            return {"priority":"P2", "reason":"uat/sandbox_issue"}
    if hit(kw_p2):
        return {"priority":"P2", "reason":"degradation_or_process"}

    return {"priority":"P3", "reason":"normal"}
