from __future__ import annotations
import os, json, re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

__all__ = [
    "load_default_ruleset",
    "detect",
    "compile_ruleset",
    "expand_aliases",
]

# --- 內建最小規則（離線安全，可被環境變數覆寫） ---
_BUILTIN = {
    "spam_keywords": [
        "buy now", "free money", "lottery", "xxx",
        "大優惠", "點我領取", "快速致富",
    ],
    "phish_keywords": [
        "verify your account", "reset 2fa", "bank",
        "crypto", "password", "click here",
        "附件.zip", "invoice.zip",
    ],
    # 別名（alias）會展開併入 spam_keywords/phish_keywords
    "aliases": {
        "spam": ["超值", "免運", "限時搶購"],
        "phish": ["安全驗證", "密碼重置", "帳戶驗證"],
    },
    # ENS 判定：任一命中即 ENS=1（簡化版，符合單元測試期待）
    "ens": {"spam_any": True, "phish_any": True},
}

_CACHE: Dict[str, Any] = {}

@dataclass
class Compiled:
    spam: List[re.Pattern]
    phish: List[re.Pattern]

def expand_aliases(rs: Dict[str, Any]) -> Dict[str, Any]:
    rs = json.loads(json.dumps(rs))  # 深拷貝
    for k, toks in rs.get("aliases", {}).items():
        if k == "spam":
            rs.setdefault("spam_keywords", [])
            rs["spam_keywords"].extend(toks)
        elif k == "phish":
            rs.setdefault("phish_keywords", [])
            rs["phish_keywords"].extend(toks)
    # 去重、正規化
    rs["spam_keywords"] = sorted(set(t.strip().lower() for t in rs.get("spam_keywords", [])))
    rs["phish_keywords"] = sorted(set(t.strip().lower() for t in rs.get("phish_keywords", [])))
    return rs

def load_default_ruleset() -> Dict[str, Any]:
    """
    測試用 API：回傳可用規則集
    - 若設了環境變數 SMA_MAILGUARD_RULESET（指向 JSON 檔），用該檔案
    - 否則用內建 _BUILTIN
    """
    if "ruleset" in _CACHE:
        return _CACHE["ruleset"]
    path = os.environ.get("SMA_MAILGUARD_RULESET")
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                rs = json.load(f)
        except Exception:
            rs = _BUILTIN
    else:
        rs = _BUILTIN
    rs = expand_aliases(rs)
    _CACHE["ruleset"] = rs
    return rs

def compile_ruleset(rs: Dict[str, Any]) -> Compiled:
    def to_patterns(tokens: List[str]) -> List[re.Pattern]:
        pats = []
        for t in tokens:
            if not t: 
                continue
            # 單純子字串比對（忽略大小寫）；避免貪婪，使用 re.escape
            pats.append(re.compile(re.escape(t), re.IGNORECASE))
        return pats
    return Compiled(
        spam=to_patterns(rs.get("spam_keywords", [])),
        phish=to_patterns(rs.get("phish_keywords", [])),
    )

def _match_any(pats: List[re.Pattern], text: str) -> Tuple[bool, List[str]]:
    hits = []
    for p in pats:
        if p.search(text):
            hits.append(p.pattern)
    return (len(hits) > 0, hits)

def detect(text: str, **kw) -> Dict[str, Any]:
    """
    測試用主函式：
    - 回傳 {"spam": bool, "phish": bool, "ens": 0/1, "spam_hits": [...], "phish_hits": [...]}
    - 預設規則：任一命中則 ENS=1（與單測『偵測』/『gating+alias』預期一致）
    """
    text = (text or "")
    rs = kw.get("ruleset") or load_default_ruleset()
    cmpd = compile_ruleset(rs)
    spam, spam_hits = _match_any(cmpd.spam, text)
    phish, phish_hits = _match_any(cmpd.phish, text)

    # ENS：只要符合 spam_any 或 phish_any 其中之一
    ens = 1 if ((rs.get("ens", {}).get("spam_any") and spam) or (rs.get("ens", {}).get("phish_any") and phish)) else 0

    return {
        "spam": bool(spam),
        "phish": bool(phish),
        "ens": int(ens),
        "spam_hits": spam_hits,
        "phish_hits": phish_hits,
        "ruleset_size": {
            "spam": len(rs.get("spam_keywords", [])),
            "phish": len(rs.get("phish_keywords", [])),
        }
    }

# --- compat: expose submodule `ai_rpa.mailguard.detector` without turning into a package ---
import sys as _sys, types as _types
_detector = _types.ModuleType("ai_rpa.mailguard.detector")
# 將主要 API 轉接到子模組
for _n in ("load_default_ruleset","detect","compile_ruleset","expand_aliases"):
    try:
        setattr(_detector, _n, globals()[_n])
    except KeyError:
        pass
# 讓 `from ai_rpa.mailguard import detector` 與 `import ai_rpa.mailguard.detector` 都可用
_sys.modules.setdefault("ai_rpa.mailguard.detector", _detector)
detector = _detector

# --- compat: expose submodule `ai_rpa.mailguard.detector` without turning into a package ---
import sys as _sys, types as _types
_detector = _types.ModuleType("ai_rpa.mailguard.detector")
# 將主要 API 轉接到子模組
for _n in ("load_default_ruleset","detect","compile_ruleset","expand_aliases"):
    try:
        setattr(_detector, _n, globals()[_n])
    except KeyError:
        pass
# 讓 `from ai_rpa.mailguard import detector` 與 `import ai_rpa.mailguard.detector` 都可用
_sys.modules.setdefault("ai_rpa.mailguard.detector", _detector)
detector = _detector
