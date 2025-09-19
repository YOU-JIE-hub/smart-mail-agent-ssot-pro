#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
python - <<'PY'
import sys, runpy, pathlib, re
# --- 關鍵：把訓練時用到的同名符號塞進 __main__ ---
import __main__
from scipy import sparse as sp

# 6 維規則特徵（與你之前一致的語義；只要維度=6就能與分類器對齊）
_KW = {
  "biz_quote":      ("報價","報價單","估價","quote","quotation","estimate"),
  "tech_support":   ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住"),
  "complaint":      ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","客服太慢"),
  "policy_qa":      ("隱私","政策","條款","合約","dpa","gdpr","資安","法遵","合規","續約","nda"),
  "profile_update": ("變更","更新","修改","變更資料","帳號","密碼","email","電話","地址"),
}
_URL_RE = re.compile(r"https?://|\.(zip|exe|js|vbs|bat|cmd|lnk|iso|docm|xlsm|pptm)\b", re.I)

def rules_feat(texts):
    rows, cols, data = [], [], []
    def hit(t, keys): return any(k in t for k in keys)
    for i, t in enumerate(texts):
        tl = (t or "").lower()
        j=0
        for key in ("biz_quote","tech_support","complaint","policy_qa","profile_update"):
            if hit(tl, _KW[key]): rows.append(i); cols.append(j); data.append(1.0)
            j+=1
        # 第 6 維：link_or_attach（URL 或高風險副檔名）
        if _URL_RE.search(tl): rows.append(i); cols.append(j); data.append(1.0)
    n=len(texts)
    if not data:  # 沒命中時也要保持 (n,6)
        return sp.csr_matrix((n,6), dtype="float64")
    return sp.csr_matrix((data,(rows,cols)), shape=(n,6), dtype="float64")

class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features=int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((X.shape[0], self.n_features), dtype="float64")

class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((len(X), 0), dtype="float64")

__main__.rules_feat = rules_feat
__main__.ZeroPad = ZeroPad
__main__.DictFeaturizer = DictFeaturizer

# --- 以 __main__ 身份執行你的 router ---
sys.argv = [
    "runtime_threshold_router.py",
    "--model", "artifacts/intent_pro_cal.pkl",
    "--input", "data/intent/external_realistic_test.clean.jsonl",
    "--out_preds", "reports_auto/intent_preds.jsonl",
    "--eval"
]
runpy.run_path(str(pathlib.Path(".sma_tools")/"runtime_threshold_router.py"), run_name="__main__")
PY
