from __future__ import annotations
import os, time
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import joblib

from service.schemas import PredictIn, PredictOut, TopKItem
from service.middleware import timing_middleware
from runtime_preproc import normalize_text  # must exist in your repo

app = FastAPI(title="Smart Mail Agent (Pro)", version="0.1.0")
app.middleware("http")(timing_middleware)

REQS = Counter("sma_requests_total", "Total requests", ["route"])
ERRS = Counter("sma_errors_total", "Errors total", ["route","type"])
LAT = Histogram("sma_latency_ms", "Latency (ms)", ["route"], buckets=(5,10,20,50,100,200,500,1000,2000))
ABSTAIN = Counter("sma_abstain_total", "Abstained predictions", ["task"])
INFER_PROB = Histogram("sma_top1_prob", "Top1 probability", ["task"], buckets=(.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0))
READY = Gauge("sma_ready", "Readiness flag")

_MODELS: Dict[str, object] = {}

def load_model(task: str):
    if task in _MODELS:
        return _MODELS[task]
    path = os.environ.get("INTENT_PKL") if task == "intent" else os.environ.get("SPAM_PKL")
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"{task.upper()}_PKL not set or not found: {path!r}")
    _MODELS[task] = joblib.load(path)
    return _MODELS[task]

def predict_one(task: str, text: str, top_k: int, abstain_min_conf: float | None) -> PredictOut:
    model = load_model(task)
    t = normalize_text(text, task=task)
    y = model.predict([t])[0]
    topk: List[TopKItem] = []
    try:
        proba = model.predict_proba([t])[0]
        labels = getattr(model, "classes_", None)
        if labels is not None:
            pairs = sorted(zip(labels, proba), key=lambda x: float(x[1]), reverse=True)[:top_k]
            topk = [TopKItem(label=str(a), p=float(b)) for a,b in pairs]
    except Exception:
        pass
    pred = str(y)
    abstained = False
    if abstain_min_conf is not None and topk:
        if topk[0].p < float(abstain_min_conf):
            abstained = True
            pred = None
    return PredictOut(task=task, text=t, pred=pred, topk=topk, abstained=abstained)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ready")
def ready():
    ready_intent = int(bool(os.environ.get("INTENT_PKL") and os.path.exists(os.environ["INTENT_PKL"])))
    ready_spam = int(bool(os.environ.get("SPAM_PKL") and os.path.exists(os.environ["SPAM_PKL"])))
    READY.set(1.0 if (ready_intent or ready_spam) else 0.0)
    return {"intent": ready_intent, "spam": ready_spam}

@app.post("/v1/predict", response_model=PredictOut)
def api_predict(body: PredictIn):
    route = "/v1/predict"
    REQS.labels(route).inc()
    start = time.perf_counter()
    try:
        abstain_min_conf = os.getenv("ABSTAIN_MIN_CONF")
        amc = float(abstain_min_conf) if abstain_min_conf not in (None, "") else None
        out = predict_one(body.task, body.text, body.top_k, amc)
        if out.topk:
            INFER_PROB.labels(body.task).observe(out.topk[0].p)
        if out.abstained:
            ABSTAIN.labels(body.task).inc()
        return out
    except FileNotFoundError as e:
        ERRS.labels(route, "model_missing").inc()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        ERRS.labels(route, "internal").inc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        LAT.labels(route).observe((time.perf_counter() - start) * 1000.0)

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
