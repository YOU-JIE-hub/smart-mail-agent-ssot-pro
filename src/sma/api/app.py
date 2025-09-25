from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os, json, time, pathlib, traceback

from sma.common.config import env_path, classes_fallback, sha256_file  # type: ignore

APP = FastAPI(title="sma-api", version="1.0")
CRASH_ROOT = pathlib.Path("reports_auto/crash")
CRASH_ROOT.mkdir(parents=True, exist_ok=True)

# ---- utilities ----
def _now_ts() -> str: return time.strftime("%Y%m%dT%H%M%S", time.localtime())
def _mk_run() -> pathlib.Path:
    p = CRASH_ROOT / _now_ts()
    p.mkdir(parents=True, exist_ok=True)
    (CRASH_ROOT / "latest").unlink(missing_ok=True)
    (CRASH_ROOT / "latest").symlink_to(p, target_is_directory=True)
    return p

def _dump_err(run: pathlib.Path, kind: str, info: Dict[str, Any]) -> None:
    (run / f"{kind}_error.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

def _norm_proba(arr, n_samples: int):
    import numpy as np
    a = arr
    if isinstance(a, list):
        a = np.column_stack([np.ravel(x).astype(float) for x in a])  # -> (n_samples, n_classes)
    a = np.asarray(a)
    if a.ndim == 1:  # binary -> [1-p, p]
        p = a.astype(float).ravel()
        a = np.column_stack([1.0 - p, p])
    if a.shape[0] != n_samples and a.shape[1] == n_samples:
        a = a.T
    return a

# ---- models cache ----
_INTENT_READY = False
_INTENT_META: Dict[str, Any] = {}
_INTENT_CLASSES: List[str] = []

_SPAM = None
_SPAM_PATH: Optional[str] = None

_KIE = {"tok": None, "mdl": None, "dir": None}

def _intent_load() -> Dict[str, Any]:
    global _INTENT_READY, _INTENT_META, _INTENT_CLASSES
    try:
        from sma.common import intent_compat as ic  # type: ignore
        from sma.common.intent_compat import load_pipeline, meta  # type: ignore
    except Exception as e:
        raise HTTPException(500, f"intent_compat import error: {e}")

    p = env_path("INTENT_PKL")
    if not p or not p.exists():
        raise HTTPException(500, f"INTENT_PKL not found: {p}")

    load_pipeline(str(p))
    m = meta() or {}
    m.setdefault("path", str(p))
    _INTENT_META = m
    _INTENT_CLASSES = m.get("classes_", []) or classes_fallback()
    _INTENT_READY = True
    return m

def _intent_predict(text: str) -> Dict[str, Any]:
    global _INTENT_CLASSES
    from sma.common import intent_compat as ic  # type: ignore
    try:
        # 優先走 predict_proba_batch；若缺就 fallback 到 _pipe
        try:
            from sma.common.intent_compat import predict_proba_batch  # type: ignore
            proba, classes = predict_proba_batch([text])  # type: ignore
        except Exception:
            pipe = getattr(ic, "_pipe", None)
            if pipe is None:
                raise RuntimeError("intent pipeline not loaded")
            proba = pipe.predict_proba([text])
            classes = _INTENT_CLASSES
        P = _norm_proba(proba, 1)[0]
        import numpy as np
        idx = int(np.argmax(P))
        label = (_INTENT_CLASSES or classes or [])
        label = label[idx] if (label and 0 <= idx < len(label)) else idx
        score = float(P[idx])
        return {"label": label, "score": score, "meta": _INTENT_META}
    except Exception as e:
        run = _mk_run()
        _dump_err(run, "intent", {"error": str(e), "traceback": traceback.format_exc(), "text": text, "meta": _INTENT_META})
        raise HTTPException(500, f"intent error: {e}")

def _spam_predict(text: str) -> Dict[str, Any]:
    global _SPAM, _SPAM_PATH
    try:
        from joblib import load  # type: ignore
        q = env_path("SPAM_PKL")
        if not q or not q.exists(): raise HTTPException(500, f"SPAM_PKL not found: {q}")
        if _SPAM is None or _SPAM_PATH != str(q):
            _SPAM = load(str(q)); _SPAM_PATH = str(q)
        proba = _SPAM.predict_proba([text])[0]
        score = float(proba[1]) if len(proba) > 1 else float(proba[0])
        thr = float(os.getenv("SMA_SPAM_THRESHOLD", "0.55"))
        return {"label": int(score >= thr), "score": score, "threshold": thr, "model": _SPAM_PATH}
    except Exception as e:
        run = _mk_run()
        _dump_err(run, "spam", {"error": str(e), "traceback": traceback.format_exc(), "text": text})
        raise HTTPException(500, f"spam error: {e}")

def _kie_ready() -> bool:
    q = env_path("KIE_DIR")
    return bool(q and q.exists() and (q / "config.json").exists())

def _kie_predict(text: str) -> Dict[str, Any]:
    try:
        import torch  # type: ignore
        from transformers import AutoTokenizer, AutoModelForTokenClassification  # type: ignore
        if _KIE["tok"] is None or _KIE["mdl"] is None:
            if not _kie_ready(): raise HTTPException(500, f"KIE_DIR invalid: {env_path('KIE_DIR')}")
            q = env_path("KIE_DIR")
            _KIE["tok"] = AutoTokenizer.from_pretrained(str(q), use_fast=True)
            _KIE["mdl"] = AutoModelForTokenClassification.from_pretrained(str(q))
            _KIE["dir"] = str(q)
        tok, mdl = _KIE["tok"], _KIE["mdl"]
        enc = tok(text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            logits = mdl(**enc).logits[0]; prob = logits.softmax(-1)
            ids = prob.argmax(-1).tolist(); conf = prob.max(-1).values.tolist()
        toks = tok.convert_ids_to_tokens(enc["input_ids"][0].tolist())
        return {"n_labels": int(logits.shape[-1]), "tokens": toks, "label_ids": ids, "conf": [float(x) for x in conf], "dir": _KIE["dir"]}
    except Exception as e:
        run = _mk_run()
        _dump_err(run, "kie", {"error": str(e), "traceback": traceback.format_exc(), "text": text})
        raise HTTPException(500, f"kie error: {e}")

# ---- schemas ----
class PredictReq(BaseModel):
    text: str

# ---- routes ----
@APP.get("/healthz")
def healthz(): return {"ok": True, "ts": time.time()}

@APP.get("/readyz")
def readyz():
    _intent_load()
    return {"ok": True}

@APP.get("/debug/models")
def debug_models():
    snap = {"_service_file": __file__, "_cwd": os.getcwd()}
    ip = env_path("INTENT_PKL"); sp = env_path("SPAM_PKL"); kd = env_path("KIE_DIR")
    if ip and ip.exists():
        try:
            sha = sha256_file(ip)
        except Exception:
            sha = None
        snap["intent_path"] = str(ip)
        snap["intent_sha256"] = sha
        try:
            snap["intent_meta"] = _intent_load()
        except Exception as e:
            snap["intent_err"] = f"{type(e).__name__}: {e}"
    snap["intent_classes"] = classes_fallback()
    snap["spam_path"] = str(sp) if sp else None
    snap["kie_dir"] = str(kd) if kd else None
    snap["kie_ready"] = _kie_ready()
    return snap

@APP.post("/v1/predict/intent")
def predict_intent(req: PredictReq):
    if not _INTENT_READY: _intent_load()
    return {"task": "intent", "text": req.text, **_intent_predict(req.text)}

@APP.post("/v1/predict/spam")
def predict_spam(req: PredictReq):
    return {"task": "spam", "text": req.text, **_spam_predict(req.text)}

@APP.post("/v1/predict/kie")
def predict_kie(req: PredictReq):
    if not _kie_ready(): raise HTTPException(500, f"KIE_DIR invalid or missing files: {env_path('KIE_DIR')}")
    return {"task": "kie", "text": req.text, **_kie_predict(req.text)}
