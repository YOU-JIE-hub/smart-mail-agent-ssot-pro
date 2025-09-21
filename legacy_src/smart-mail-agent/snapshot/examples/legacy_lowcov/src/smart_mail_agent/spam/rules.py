from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

CONF_PATH = Path(__file__).resolve().parents[2] / "configs" / "spam_rules.yaml"
_CACHE = {"mtime": None, "rules": None}

_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)


def _default_rules() -> dict[str, Any]:
    # 與預設 YAML 對齊
    return {
        "keywords": {
            "GET RICH QUICK": 6,
            "FREE": 2,
            "GIVEAWAY": 3,
            "CRYPTO": 2,
            "PASSWORD RESET": 2,
            "VERIFY YOUR ACCOUNT": 3,
            "URGENT": 2,
        },
        "suspicious_domains": ["bit.ly", "tinyurl.com", "goo.gl", "is.gd", "t.co"],
        "suspicious_tlds": ["tk", "gq", "ml", "cf", "ga", "top"],
        "bad_extensions": [".js", ".vbs", ".exe", ".bat", ".cmd", ".scr"],
        "whitelist_domains": ["yourcompany.com", "example.com"],
        "weights": {
            "url_suspicious": 4,
            "tld_suspicious": 3,
            "attachment_executable": 5,
            "sender_black": 5,
        },
        "thresholds": {"suspect": 4, "spam": 8},
    }


def _load_yaml_or_json(text: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except Exception:
            pass
    # JSON 兼容
    return json.loads(text)


def load_rules(force: bool = False) -> dict[str, Any]:
    """熱重載：檔案 mtime 變動即重新載入。"""
    try:
        mtime = CONF_PATH.stat().st_mtime
        if force or _CACHE["rules"] is None or _CACHE["mtime"] != mtime:
            data = _load_yaml_or_json(CONF_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data:
                data = _default_rules()
            _CACHE["rules"] = data
            _CACHE["mtime"] = mtime
    except FileNotFoundError:
        _CACHE["rules"] = _default_rules()
        _CACHE["mtime"] = None
    return _CACHE["rules"]  # type: ignore[return-value]


def score_email(
    sender: str, subject: str, content: str, attachments: list[str]
) -> tuple[int, list[str]]:
    r = load_rules()
    score = 0
    reasons: list[str] = []

    sender = (sender or "").strip().lower()
    subject_u = (subject or "").upper()
    content_u = (content or "").upper()

    # 1) 白名單網域
    domain = sender.split("@")[-1] if "@" in sender else sender
    domain = (domain or "").lower()
    if domain and any(domain.endswith(w) for w in r.get("whitelist_domains", [])):
        # 白名單不直接歸 legit，仍然保留下方檢查（避免白名單被濫用）
        pass

    # 2) 關鍵詞
    kw = r.get("keywords", {})
    for k, s in kw.items():
        if k in subject_u or k in content_u:
            score += int(s)
            reasons.append(f"keyword:{k}")

    # 3) URL 可疑（網域、TLD）
    w = r.get("weights", {})
    u = _URL_RE.findall(content or "")
    susp_domains = {d.lower() for d in r.get("suspicious_domains", [])}
    susp_tlds = {t.lower() for t in r.get("suspicious_tlds", [])}
    for url in u:
        host = url.split("://", 1)[-1].split("/", 1)[0].lower()
        if any(host == d or host.endswith("." + d) for d in susp_domains):
            score += int(w.get("url_suspicious", 0))
            reasons.append(f"url:{host}")
        tld = host.rsplit(".", 1)[-1]
        if tld in susp_tlds:
            score += int(w.get("tld_suspicious", 0))
            reasons.append(f"tld:.{tld}")

    # 4) 附件可執行
    bad_exts = [e.lower() for e in r.get("bad_extensions", [])]
    for a in attachments or []:
        ext = a.lower().rsplit(".", 1)
        ext = "." + ext[-1] if len(ext) == 2 else ""
        if ext in bad_exts:
            score += int(w.get("attachment_executable", 0))
            reasons.append(f"attachment:{ext}")

    return score, reasons


def label_email(
    sender: str, subject: str, content: str, attachments: list[str]
) -> tuple[str, int, list[str]]:
    r = load_rules()
    score, reasons = score_email(sender, subject, content, attachments)
    th = r.get("thresholds", {"suspect": 4, "spam": 8})
    label = (
        "spam"
        if score >= int(th.get("spam", 8))
        else ("suspect" if score >= int(th.get("suspect", 4)) else "legit")
    )
    return label, score, reasons
