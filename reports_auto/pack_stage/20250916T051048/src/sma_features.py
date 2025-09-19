from __future__ import annotations
from pathlib import Path
from typing import Any, List
import json, re
import numpy as np
from scipy import sparse as sp

_SPEC = Path("artifacts_prod/intent_feature_spec.json")

def _spec():
    if _SPEC.exists():
        try: return json.loads(_SPEC.read_text(encoding="utf-8"))
        except Exception: pass
    return {"dims":{"rules":7,"prio":0,"bias":0}}

def _as_text_list(X: Any) -> List[str]:
    if isinstance(X, (str, bytes)):
        return [X.decode("utf-8","ignore") if isinstance(X,bytes) else X]
    try: iter(X)
    except Exception: return [str(X)]
    out=[]
    for it in X:
        if isinstance(it, dict):
            t = " ".join(str(it.get(k,"") or "") for k in ("subject","body","text"))
        elif isinstance(it, (list,tuple)):
            t = " ".join(str(x) for x in it if isinstance(x,(str,bytes)))
        else:
            t = str(it)
        out.append(t)
    return out

# 規則對應：7 維
# 0: quote/biz_quote, 1: complaint, 2: tech_support, 3: policy_qa,
# 4: profile_update, 5: other/general, 6: has_ticket_or_order
_PATTERNS = [
    r"(報價|詢價|報價單|單價|price|quote|quotation|pricing|rfq)",
    r"(投訴|客訴|抱怨|申訴|退款|退費|退貨|chargeback|延遲|拖延|慢|毀損|損壞|damag|refund|complaint|delay)",
    r"(技術支援|技支|當機|故障|掛了|錯誤|錯碼|無法|連不上|登入|ticket|工單|bug|crash|issue|support|tech)",
    r"(規則|政策|條款|規範|合規|SLA|policy|terms|rule)",
    r"(資料異動|更新資料|變更|更正|改地址|改電話|改名|profile|account ?update|update info)",
    r"(一般|詢問|請益|hello|hi|您好|哈囉|greetings|general)",
    r"(?:ticket|工單|order|單號)[：: ]?[A-Za-z0-9_-]{3,}",
]

def rules_feat(X: Any):
    L = _as_text_list(X)
    d = _spec().get("dims",{}).get("rules",7) or 7
    Z = np.zeros((len(L), d), dtype=np.float64)
    for i, t in enumerate(L):
        for j, pat in enumerate(_PATTERNS[:d]):
            if re.search(pat, t, flags=re.I):
                Z[i, j] = 1.0
    return sp.csr_matrix(Z)

# prio/bias：保持 0 維（或依 spec），返回 CSR 零矩陣（避免 object）
def _zeros(n: int, d: int):
    if d <= 0: return sp.csr_matrix((n, 0), dtype=np.float64)
    return sp.csr_matrix((n, d), dtype=np.float64)

def prio_feat(X: Any):  return _zeros(len(_as_text_list(X)), _spec().get("dims",{}).get("prio",0))
def bias_feat(X: Any):  return _zeros(len(_as_text_list(X)), _spec().get("dims",{}).get("bias",0))
