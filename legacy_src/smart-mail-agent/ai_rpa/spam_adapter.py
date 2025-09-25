from __future__ import annotations
from typing import Dict

__all__ = ["predict_ens","predict_labels"]

# 極簡：只要含有高風險關鍵字就 ENS=1
_SPAM_TOKS = ("buy now","free money","lottery","xxx","大優惠","點我領取","快速致富")
_PHISH_TOKS = ("verify your account","reset 2fa","password","bank","click here","附件.zip","invoice.zip")

def _hit(text: str, toks) -> bool:
    t = (text or "").lower()
    return any(tok in t for tok in toks)

def predict_ens(text: str) -> int:
    return 1 if (_hit(text,_SPAM_TOKS) or _hit(text,_PHISH_TOKS)) else 0

def predict_labels(text: str) -> Dict[str,int]:
    # 提供簡單分數，給 pad 類測試使用
    return {
        "spam": int(_hit(text,_SPAM_TOKS)),
        "phish": int(_hit(text,_PHISH_TOKS)),
        "ens": predict_ens(text),
    }
