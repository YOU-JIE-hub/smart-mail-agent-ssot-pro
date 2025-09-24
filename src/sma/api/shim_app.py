from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Tuple
import os, time

app = FastAPI(title="SSOT Pro Shim")

# ---- healthz/readyz ----
@app.get("/health")  # for older
@app.get("/healthz")
def healthz(): return {"ok": True, "ts": time.time()}

@app.get("/ready")   # for older
@app.get("/readyz")
def readyz(): return {"ok": True, "ts": time.time()}

# ---- payload ----
class TextIn(BaseModel):
    text: str

# ---- optional spam/intent (簡單 heuristic；保留你已經可用的 API 形狀) ----
@app.post("/v1/predict/spam")
def spam_pred(p: TextIn) -> Dict[str, Any]:
    t = p.text.lower()
    score = 0.5 + 0.5*float(any(k in t for k in ["free","prize","win","bitcoin","點我"]))
    return {"label": "spam" if score>=float(os.getenv("SMA_SPAM_THRESHOLD","0.55")) else "ham",
            "score": score}

@app.post("/v1/predict/intent")
def intent_pred(p: TextIn) -> Dict[str, Any]:
    t = p.text
    if any(x in t for x in ["退款","退貨","折讓"]): return {"label":"refund","score":0.9}
    if any(x in t for x in ["報價","費用","價格"]): return {"label":"quotation","score":0.8}
    return {"label":"other","score":0.5}

# ---- real KIE (transformers) ----
KIE_DIR = os.getenv("KIE_DIR", "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model")
_kie = {"ok": False}

def _load_kie():
    if _kie.get("ok"): return
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForTokenClassification
        tok = AutoTokenizer.from_pretrained(KIE_DIR, use_fast=True)
        mdl = AutoModelForTokenClassification.from_pretrained(KIE_DIR)
        mdl.eval()
        _kie.update(tok=tok, mdl=mdl, id2label=mdl.config.id2label, ok=True)
    except Exception as e:
        _kie.update(ok=False, err=str(e))

def _spans_from_logits(text:str, offsets:List[Tuple[int,int]], logits) -> List[Dict[str,Any]]:
    import torch
    probs = torch.softmax(logits, dim=-1)
    idx   = torch.argmax(probs, dim=-1).tolist()  # [seq]
    labels= [_kie["id2label"].get(i,str(i)) for i in idx]
    out=[]
    cur=None
    for lab,(s,e) in zip(labels, offsets):
        if s==0 and e==0:  # special tokens
            continue
        if lab and lab!="O":
            if cur and cur["label"]==lab and s==cur["end"]:
                cur["end"]=e
            else:
                if cur: out.append(cur); cur=None
                cur={"label":lab,"start":s,"end":e}
        else:
            if cur: out.append(cur); cur=None
    if cur: out.append(cur)
    # attach snippet & dummy score (avg max prob)
    ents=[]
    for span,(lab,(s,e)) in zip(out, [(x["label"],(x["start"],x["end"])) for x in out]):
        ents.append({"label":lab,"start":s,"end":e,"text":text[s:e]})
    return ents

@app.post("/v1/predict/kie")
def kie_pred(p: TextIn) -> Dict[str, Any]:
    _load_kie()
    if not _kie.get("ok"):
        return {"ok": False, "error":"kie_not_loaded", "detail": _kie.get("err")}
    import torch
    tok = _kie["tok"]; mdl=_kie["mdl"]
    enc = tok(p.text, return_offsets_mapping=True, return_tensors="pt", truncation=True)
    offsets = enc.pop("offset_mapping")[0].tolist()
    with torch.no_grad():
        logits = mdl(**enc).logits[0]
    ents = _spans_from_logits(p.text, offsets, logits)
    return {"ok": True, "tokenizer": type(tok).__name__, "n_labels": len(_kie["id2label"]), "entities": ents}
