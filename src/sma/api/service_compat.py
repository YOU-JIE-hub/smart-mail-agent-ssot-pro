from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os, time, pathlib, traceback

def env_path(name: str) -> Optional[pathlib.Path]:
    v=os.getenv(name); return pathlib.Path(v).expanduser().resolve() if v else None

app = FastAPI(title="sma-service-compat", version="1.0")

# --- globals for spam lazy-load ---
_SPAM=None; _SPAM_PATH=None

# --- intent helpers ---
def _intent_load_meta() -> Dict[str, Any]:
    try:
        from sma.common.intent_compat import load_pipeline, meta
        p = env_path("INTENT_PKL")
        if not p or not p.exists(): raise HTTPException(500, f"INTENT_PKL not found: {p}")
        load_pipeline(str(p))
        m = meta()
        m["_service_file"] = __file__
        return m
    except Exception as e:
        raise HTTPException(500, f"intent load error: {e}")

def _intent_predict(text: str) -> Dict[str, Any]:
    try:
        from sma.common.intent_compat import predict_proba_batch, meta
        import numpy as np
        proba, classes = predict_proba_batch([text])
        p = proba[0]; idx=int(np.argmax(p))
        label = classes[idx] if classes and idx < len(classes) else idx
        return {"label": label, "score": float(p[idx]), "meta": meta()}
    except Exception as e:
        raise HTTPException(500, f"intent predict error: {e}")

# --- spam ---
def _spam_predict(text: str) -> Dict[str,Any]:
    global _SPAM,_SPAM_PATH
    try:
        from joblib import load
        q=env_path("SPAM_PKL")
        if not q or not q.exists(): raise HTTPException(500, f"SPAM_PKL not found: {q}")
        if _SPAM is None or _SPAM_PATH != str(q):
            _SPAM=load(str(q)); _SPAM_PATH=str(q)
        proba=_SPAM.predict_proba([text])[0]
        score=float(proba[1]) if len(proba)>1 else float(proba[0])
        thr=float(os.getenv("SMA_SPAM_THRESHOLD","0.55"))
        return {"label": int(score>=thr), "score": score, "threshold": thr, "model": _SPAM_PATH}
    except Exception as e:
        raise HTTPException(500, f"spam predict error: {e}")

# --- kie (存在性健檢 + 直接丟 HF 模型 logits，與你之前一致) ---
def _kie_predict(text: str) -> Dict[str,Any]:
    import torch
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    q=env_path("KIE_DIR")
    if not q or not q.exists(): raise HTTPException(500, f"KIE_DIR invalid: {q}")
    tok=AutoTokenizer.from_pretrained(str(q),use_fast=True)
    mdl=AutoModelForTokenClassification.from_pretrained(str(q))
    enc=tok(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        logits=mdl(**enc).logits[0]; prob=logits.softmax(-1)
    toks=tok.convert_ids_to_tokens(enc["input_ids"][0].tolist())
    ids=prob.argmax(-1).tolist(); conf=prob.max(-1).values.tolist()
    return {"n_labels": int(logits.shape[-1]), "tokens": toks, "label_ids": ids, "conf": [float(x) for x in conf], "dir": str(q)}

class PredictReq(BaseModel): text: str

# --- health/ready (每個 decorator 各一行，避免語法雷) ---
@app.get("/healthz")
def healthz(): return {"ok": True, "ts": time.time()}

@app.get("/readyz")
def readyz(): _=_intent_load_meta(); return {"ok": True}

@app.get("/debug/models")
def debug_models():
    snap={"_service_file": __file__}
    try: snap["intent_meta"]=_intent_load_meta()
    except Exception as e: snap["intent_err"]=f"{type(e).__name__}: {e}"
    for k in ["INTENT_PKL","SPAM_PKL","KIE_DIR"]:
        v=os.getenv(k);  snap[k.lower()]=v
    return snap

@app.post("/v1/predict/intent")
def predict_intent(req: PredictReq):
    return {"task":"intent","text":req.text, **_intent_predict(req.text)}

@app.post("/v1/predict/spam")
def predict_spam(req: PredictReq):
    return {"task":"spam","text":req.text, **_spam_predict(req.text)}

@app.post("/v1/predict/kie")
def predict_kie(req: PredictReq):
    return {"task":"kie","text":req.text, **_kie_predict(req.text)}
