from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os, json, time, pathlib, traceback, uuid

SIG = "svc_final_v1"
APP_LOG = pathlib.Path("reports_auto/logs/service_compat.log"); APP_LOG.parent.mkdir(parents=True, exist_ok=True)
ERR_DIR = pathlib.Path("reports_auto/logs/errors"); ERR_DIR.mkdir(parents=True, exist_ok=True)

def _log(msg:str):
    try:
        with APP_LOG.open("a", encoding="utf-8") as f: f.write(msg+"\n")
    except Exception: pass

# --- .env 覆寫 ---
def _load_env(path=".env"):
    p = pathlib.Path(path)
    if not p.exists(): return
    for line in p.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1)
        os.environ[k.strip()]=v.strip()
_load_env()  # 立即覆寫，忽略外部殘留 INTENT_PKL

def env_path(name: str) -> Optional[pathlib.Path]:
    v=os.getenv(name); return pathlib.Path(v).expanduser().resolve() if v else None

app = FastAPI(title="sma-service", version="0.9")

# --- INTENT ---
_INTENT_READY=False
def _intent_load() -> Dict[str,Any]:
    global _INTENT_READY
    from sma.common.intent_compat import load_pipeline, meta
    p = env_path("INTENT_PKL")
    if not p or not p.exists(): raise HTTPException(500, f"INTENT_PKL not found: {p}")
    info = load_pipeline(str(p))
    _INTENT_READY=True
    return info

def _resolve_classes() -> list[str]:
    # meta -> env fallback
    try:
        from sma.common.intent_compat import meta
        m = meta() or {}
        cls = m.get("classes_") or []
        if cls: return [str(x) for x in cls]
    except Exception: pass
    import json as _json, os as _os
    try:
        return list(_json.loads(_os.getenv("INTENT_CLASSES_JSON","[]")))
    except Exception:
        return []

def _intent_predict(text: str) -> Dict[str,Any]:
    from sma.common.intent_compat import predict_proba_batch
    import numpy as np
    proba, classes = predict_proba_batch([text])
    p = proba[0]; idx=int(np.argmax(p))
    labels = classes or _resolve_classes()
    label = labels[idx] if idx < len(labels) and len(labels)>0 else idx
    return {"label": label, "score": float(p[idx]), "meta": {"path": env_path("INTENT_PKL") and str(env_path("INTENT_PKL")), "classes_": labels}}

# --- SPAM ---
_SPAM=None; _SPAM_PATH=None
def _spam_predict(text: str) -> Dict[str,Any]:
    global _SPAM, _SPAM_PATH
    from joblib import load
    q=env_path("SPAM_PKL")
    if not q or not q.exists(): raise HTTPException(500, f"SPAM_PKL not found: {q}")
    if _SPAM is None or _SPAM_PATH != str(q):
        _SPAM = load(str(q)); _SPAM_PATH=str(q)
    proba=_SPAM.predict_proba([text])[0]
    score=float(proba[1]) if len(proba)>1 else float(proba[0])
    thr=float(os.getenv("SMA_SPAM_THRESHOLD","0.55"))
    return {"label": int(score>=thr), "score": score, "threshold": thr, "model": _SPAM_PATH}

# --- KIE ---
_K={"tok":None,"mdl":None,"dir":None}
def _kie_ready()->bool:
    q=env_path("KIE_DIR"); return bool(q and q.exists() and (q/"config.json").exists())
def _kie_predict(text:str)->Dict[str,Any]:
    import torch
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    if _K["tok"] is None or _K["mdl"] is None:
        if not _kie_ready(): raise HTTPException(500, f"KIE_DIR invalid: {env_path('KIE_DIR')}")
        q=env_path("KIE_DIR"); _K["tok"]=AutoTokenizer.from_pretrained(str(q),use_fast=True); _K["mdl"]=AutoModelForTokenClassification.from_pretrained(str(q)); _K["dir"]=str(q)
    tok,mdl=_K["tok"],_K["mdl"]
    enc=tok(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        logits=mdl(**enc).logits[0]; prob=logits.softmax(-1); ids=prob.argmax(-1).tolist(); conf=prob.max(-1).values.tolist()
    toks=tok.convert_ids_to_tokens(enc["input_ids"][0].tolist())
    return {"n_labels": int(logits.shape[-1]), "tokens": toks, "label_ids": ids, "conf": [float(x) for x in conf], "dir": _K["dir"]}

class PredictReq(BaseModel): text: str

@app.middleware("http")
async def catch_all(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        rid=f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        payload={"error":{"type":type(e).__name__,"message":str(e),"traceback":traceback.format_exc()},"rid":rid,"sig":SIG}
        try:
            (ERR_DIR/f"err-{rid}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception: pass
        return JSONResponse(status_code=500, content=payload)

@app.get("/healthz")
def healthz(): return {"ok": True, "ts": time.time()}
@app.get("/readyz")
def readyz(): _= _intent_load(); return {"ok": True}

@app.post("/v1/predict/intent")
def predict_intent(req: PredictReq):
    if not _INTENT_READY: _= _intent_load()
    return {"task":"intent","text":req.text, **_intent_predict(req.text)}

@app.post("/v1/predict/spam")
def predict_spam(req: PredictReq): return {"task":"spam","text":req.text, **_spam_predict(req.text)}

@app.post("/v1/predict/kie")
def predict_kie(req: PredictReq):
    if not _kie_ready(): raise HTTPException(500, f"KIE_DIR invalid or missing files: {env_path('KIE_DIR')}")
    return {"task":"kie","text":req.text, **_kie_predict(req.text)}

@app.get("/debug/env")
def debug_env():
    def read_dotenv(path=".env"):
        d={}; p=pathlib.Path(path)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k,v=line.split("=",1); d[k.strip()]=v.strip()
        return d
    return {"dotenv": read_dotenv(),
            "process_env": {k: os.getenv(k) for k in ["INTENT_PKL","SPAM_PKL","KIE_DIR","INTENT_CLASSES_JSON"] if os.getenv(k)}}

@app.get("/debug/models")
def debug_models():
    snap={"_service_file": __file__, "_cwd": os.getcwd(), "_sig": SIG}
    try:
        from sma.common.intent_compat import meta
        snap["intent_meta"]=meta()
    except Exception as e:
        snap["intent_err"]=f"{type(e).__name__}: {e}"
    snap["intent_path"]=str(env_path("INTENT_PKL")) if env_path("INTENT_PKL") else None
    snap["intent_classes"]= _resolve_classes()
    snap["spam_path"]=str(env_path("SPAM_PKL")) if env_path("SPAM_PKL") else None
    r=env_path("KIE_DIR");  snap["kie_dir"]=str(r) if r else None; snap["kie_ready"]=bool(r and (r/"config.json").exists())
    return snap
