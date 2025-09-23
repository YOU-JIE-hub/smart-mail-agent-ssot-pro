from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os, re, time

# 可選：有 joblib/ sklearn 就載模型；沒有就用 heuristic，不會壞
try:
    import joblib  # type: ignore
    _HAS_JOBLIB = True
except Exception:
    joblib = None  # type: ignore
    _HAS_JOBLIB = False

app = FastAPI(title="SMA Shim", version="1.0")

# --- 健康檢查 ---
@app.get("/health") 
def health(): return {"ok": True, "ts": time.strftime("%F %T")}

@app.get("/ready")
def ready():
    return {
        "ok": True,
        "has_joblib": _HAS_JOBLIB,
        "spam_pkl": os.getenv("SPAM_PKL", ""),
        "intent_pkl": os.getenv("INTENT_PKL", ""),
        "kie_dir": os.getenv("KIE_DIR", "")
    }

# 兼容 /healthz /readyz
@app.get("/healthz") 
def healthz(): return health()

@app.get("/readyz") 
def readyz(): return ready()

# --- 嘗試載入模型（可缺） ---
SPAM_PKL   = os.getenv("SPAM_PKL",   "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl")
INTENT_PKL = os.getenv("INTENT_PKL", "/home/youjie/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl")
KIE_DIR    = os.getenv("KIE_DIR",    "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model")
THRESH     = float(os.getenv("SMA_SPAM_THRESHOLD", "0.5"))

spam_model = None
intent_model = None
if _HAS_JOBLIB:
    try:
        if SPAM_PKL and os.path.exists(SPAM_PKL):
            spam_model = joblib.load(SPAM_PKL)
    except Exception:
        spam_model = None
    try:
        if INTENT_PKL and os.path.exists(INTENT_PKL):
            intent_model = joblib.load(INTENT_PKL)
    except Exception:
        intent_model = None

# --- I/O schema ---
class TextIn(BaseModel):
    text: str

# --- Heuristics ---
def spam_score_heuristic(text: str) -> float:
    t = (text or "").lower()
    kws = ["free", "win", "prize", "click", "limited", "優惠", "免費", "限時", "點此", "抽獎"]
    score = sum(1 for k in kws if k in t) / max(1, len(kws))
    # 粗略：有網址/金額提升一點
    if re.search(r'https?://|www\.', t): score += 0.2
    if re.search(r'\$\s*\d+|nt\$?\s*\d+|[0-9]{1,3}(?:,[0-9]{3})+', t, re.I): score += 0.1
    return float(min(0.98, max(0.02, score)))

def intent_heuristic(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["refund", "退款", "退貨"]): return "refund"
    if any(k in t for k in ["故障", "錯誤", "error", "bug", "ticket"]): return "support"
    if any(k in t for k in ["抱怨", "投訴", "escalate", "升級"]): return "complaint"
    if any(k in t for k in ["地址", "電話", "變更", "更新", "update", "crm"]): return "crm_update"
    if any(k in t for k in ["faq", "規則", "policy", "政策"]): return "faq"
    return "other"

def kie_extract(text: str) -> Dict[str, Any]:
    s = text or ""
    out: Dict[str, Any] = {"amounts": [], "phones": [], "emails": []}
    amt_pat = re.compile(r'(?:(?:NT\$|NTD|USD|\$)\s*)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]{1,2})?)')
    ph_pat  = re.compile(r'(?:\+?886-?)?0?9\d{2}-?\d{3}-?\d{3}')
    em_pat  = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
    out["amounts"] = [m.group(0) for m in amt_pat.finditer(s)][:5]
    out["phones"]  = [m.group(0) for m in ph_pat.finditer(s)][:5]
    out["emails"]  = [m.group(0) for m in em_pat.finditer(s)][:3]
    out["ok"] = True
    return out

# --- /v1/predict/spam ---
@app.post("/v1/predict/spam")
def predict_spam(inp: TextIn):
    text = inp.text or ""
    prob: Optional[float] = None
    if spam_model is not None:
        try:
            if hasattr(spam_model, "predict_proba"):
                prob = float(spam_model.predict_proba([text])[0][1])
            elif hasattr(spam_model, "decision_function"):
                # 粗略映射到 [0,1]
                import math
                d = float(spam_model.decision_function([text])[0])
                prob = 1.0/(1.0 + math.exp(-d))
        except Exception:
            prob = None
    if prob is None:
        prob = spam_score_heuristic(text)
    label = "spam" if prob >= THRESH else "ham"
    return {"ok": True, "prob": prob, "label": label, "threshold": THRESH, "model": bool(spam_model)}

# --- /v1/predict/intent ---
@app.post("/v1/predict/intent")
def predict_intent(inp: TextIn):
    text = inp.text or ""
    label = None
    score = None
    if intent_model is not None:
        try:
            label = intent_model.predict([text])[0]
            if hasattr(intent_model, "predict_proba"):
                import numpy as np  # 標準環境一般會有；沒有也不致命
                proba = intent_model.predict_proba([text])[0]
                score = float(max(proba))
        except Exception:
            label = None
    if label is None:
        label = intent_heuristic(text)
    return {"ok": True, "label": str(label), "score": score, "model": bool(intent_model)}

# --- /v1/predict/kie ---
@app.post("/v1/predict/kie")
def predict_kie(inp: TextIn):
    return kie_extract(inp.text or "")
