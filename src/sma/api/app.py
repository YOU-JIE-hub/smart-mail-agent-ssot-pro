from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
import os, re

try:
    import joblib  # optional
except Exception:
    joblib = None

SPAM_PKL   = os.getenv("SPAM_PKL",   "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl")
INTENT_PKL = os.getenv("INTENT_PKL", "/home/youjie/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl")
KIE_DIR    = os.getenv("KIE_DIR",    "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model")
SPAM_TH    = float(os.getenv("SMA_SPAM_THRESHOLD", "0.50"))

def _load_model(p: str):
    if not joblib or not p or not os.path.exists(p):
        return None
    try:
        return joblib.load(p)
    except Exception:
        return None

spam_model   = _load_model(SPAM_PKL)
intent_model = _load_model(INTENT_PKL)

app = FastAPI(title="SMA Minimal API", version="0.1.1")

class TextIn(BaseModel):
    text: str

@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"status": "ok"}

@app.get("/readyz")
def readyz() -> Dict[str, Any]:
    return {
        "spam_model":   bool(spam_model),
        "intent_model": bool(intent_model),
        "kie_dir":      os.path.isdir(KIE_DIR),
    }

@app.post("/v1/predict/spam")
def predict_spam(inp: TextIn) -> Dict[str, Any]:
    text = inp.text or ""
    score = 0.5
    if spam_model is not None:
        try:
            if hasattr(spam_model, "predict_proba"):
                score = float(spam_model.predict_proba([text])[0][1])
            elif hasattr(spam_model, "decision_function"):
                v = float(spam_model.decision_function([text])[0])
                score = 1.0/(1.0+pow(2.71828,-v))
            else:
                score = float(getattr(spam_model, "predict", lambda x:[0])([text])[0])
        except Exception:
            pass
    else:
        score = 0.9 if re.search(r"free|win|prize|限時|點我|中大奖", text, re.I) else 0.1
    label = "spam" if score >= SPAM_TH else "ham"
    return {"label": label, "score": round(score, 4), "threshold": SPAM_TH, "model_path": SPAM_PKL}

@app.post("/v1/predict/intent")
def predict_intent(inp: TextIn) -> Dict[str, Any]:
    text = (inp.text or "").lower()
    label = "other"
    if intent_model is not None:
        try:
            label = str(getattr(intent_model, "predict", lambda x:["other"])([text])[0])
        except Exception:
            label = "other"
    else:
        if re.search(r"報價|quote|price|費用", text): label = "quote"
        elif re.search(r"退款|退貨|refund|return", text): label = "refund"
        elif re.search(r"合約|contract|agreement", text): label = "contract"
        elif re.search(r"工單|ticket|support|bug|error", text): label = "support"
    return {"label": label, "model_path": INTENT_PKL}

@app.post("/v1/predict/kie")
def predict_kie(inp: TextIn) -> Dict[str, Any]:
    t = inp.text or ""
    amount = None
    m = re.search(r"(?:NT\$|\$)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(?:元|dollars)?", t)
    if m: amount = m.group(1).replace(",", "")
    invoice = None
    m = re.search(r"\b([A-Z]{2}-?\d{8})\b", t, re.I)
    if m: invoice = m.group(1).upper().replace("-", "")
    phone = None
    m = re.search(r"(?:(?:\+?886\-?)?0?9\d{2})[\-\s]?\d{3}[\-\s]?\d{3}", t)
    if m: phone = m.group(0)
    return {"fields": {"amount": amount, "invoice": invoice, "phone": phone}, "kie_dir_exists": os.path.isdir(KIE_DIR), "kie_dir": KIE_DIR}
