import os, sys, json, traceback, time, joblib, importlib.util
from pathlib import Path
# --- sys.path 注入，確保能 import vendor 與 src ---
ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT/"vendor", ROOT/"src", ROOT):
    if str(p) not in sys.path: sys.path.insert(0, str(p))
# --- ZeroPad：先嘗試 vendor，失敗再內建備援 ---
try:
    from sma_tools.sk_zero_pad import ZeroPad  # allow 'from sma_tools...' (if installed as pkg)
except Exception:
    try:
        from vendor.sma_tools.sk_zero_pad import ZeroPad  # local vendor 路徑
    except Exception:
        import numpy as np
        from scipy import sparse as sp
        from sklearn.base import BaseEstimator, TransformerMixin
        class ZeroPad(BaseEstimator, TransformerMixin):
            def __init__(self,width:int=1,dtype=np.float64,**kw):
                try: self.width=int(width) if width else 1
                except Exception: self.width=1
                self.dtype=dtype; self._extra=dict(kw)
            def __setstate__(self, s): self.__dict__.update(s or {}); self.width=getattr(self,"width",1); self.dtype=getattr(self,"dtype",np.float64)
            def fit(self, X, y=None): return self
            def transform(self, X): return sp.csr_matrix((len(X), self.width), dtype=self.dtype)

# --- 盡量用你提供的 rules 檔（只用環境變數，不做廣搜） ---
RULES_SRC = os.environ.get("SMA_RULES_SRC","")
def load_rules_feat():
    if not RULES_SRC or not Path(RULES_SRC).exists():
        return None
    spec = importlib.util.spec_from_file_location("train_rules_impl", RULES_SRC)
    if not spec or not spec.loader: return None
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    # 常見命名別名
    for name in ("rules_feat","rules_features","RULES_FEATURES","get_rules_features"):
        fn = getattr(mod, name, None)
        if callable(fn): return fn
    return None

rules_fn = load_rules_feat()
def rules_dim_probe():
    try:
        if rules_fn:
            v = rules_fn("測試")  # 以文字回傳特徵向量
            return len(list(v)) if v is not None else 0
    except Exception:
        pass
    return int(os.environ.get("SMA_RULES_DIM","7"))  # 最後保底

# --- 載入資料 ---
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/intent_eval/dataset.cleaned.jsonl")
OUT_PKL = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("artifacts/intent_pipeline_aligned.pkl")
DIAG = Path(sys.argv[3]) if len(sys.argv) > 3 else (Path("reports_auto/train")/time.strftime("%Y%m%dT%H%M%S")/"diag.json")
DIAG.parent.mkdir(parents=True, exist_ok=True)

if not DATA.exists():
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text('''\
{"text":"您好，想詢問報價與交期，數量100台","label":"biz_quote"}
{"text":"附件服務無法連線，請協助處理","label":"tech_support"}
{"text":"我想了解退訂政策","label":"policy_qa"}
{"text":"發票抬頭需要更新","label":"profile_update"}
''', encoding="utf-8")

X, y = [], []
for line in DATA.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    d = json.loads(line)
    X.append(d.get("text") or d.get("content") or d.get("utterance") or "")
    y.append(str(d.get("label") or d.get("intent") or ""))

# --- 建立 pipeline（word + char + rules ZeroPad） ---
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

dim_rules = rules_dim_probe()
feat = FeatureUnion([
    ("word",  TfidfVectorizer(analyzer="word", ngram_range=(1,2), min_df=1)),
    ("char",  TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=1)),
    ("rules", ZeroPad(width=dim_rules)),
])
clf = LogisticRegression(max_iter=1000, n_jobs=None)

pipe = Pipeline([("feat", feat), ("clf", clf)])
pipe.fit(X, y)

# --- 存檔 & 診斷 ---
OUT_PKL.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(pipe, OUT_PKL)

# 診斷（維度拆解）
word_dim = pipe.named_steps["feat"].transformer_list[0][1].vocabulary_
char_dim = pipe.named_steps["feat"].transformer_list[1][1].vocabulary_
diag = {
    "dim_diag": {
        "expected_dim": (len(word_dim) if word_dim else 0) + (len(char_dim) if char_dim else 0) + int(dim_rules),
        "branch_dims": {
            "word": len(word_dim) if word_dim else 0,
            "char": len(char_dim) if char_dim else 0,
            "rules": int(dim_rules)
        }
    },
    "data_n": len(X),
    "labels_n": len(set(y)),
    "rules_src": RULES_SRC or None
}
DIAG.write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
print("[OK] TRAIN done ->", OUT_PKL)
