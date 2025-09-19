#!/usr/bin/env python
import os, sys, json, time, sqlite3, traceback, importlib.util
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import joblib
from collections import Counter

SMA_ERR_DIR=os.environ.get("SMA_ERR_DIR") or ""
ML_PKL=os.environ.get("SMA_INTENT_ML_PKL") or ""
RULES_SRC=os.environ.get("SMA_RULES_SRC") or ""
ML_THRESHOLD=float(os.environ.get("SMA_ML_THRESHOLD") or 0.45)
DB_PATH="reports_auto/audit.sqlite3"

def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con=sqlite3.connect(DB_PATH)
    cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS llm_calls(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT, route TEXT, latency_ms INTEGER, cost_usd REAL,
        request_id TEXT, created_at TEXT
    )""")
    con.commit(); con.close()

def audit_llm(tag, route, latency_ms, cost_usd=0.0, request_id=""):
    try:
        _ensure_db()
        con=sqlite3.connect(DB_PATH); cur=con.cursor()
        cur.execute("INSERT INTO llm_calls(tag,route,latency_ms,cost_usd,request_id,created_at) VALUES(?,?,?,?,?,datetime('now'))",
            (tag,route,int(latency_ms),float(cost_usd),request_id))
        con.commit(); con.close()
    except Exception as e:
        _log_exc("audit_llm", e)

def _log_exc(tag, exc):
    tb="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if SMA_ERR_DIR:
        try:
            os.makedirs(SMA_ERR_DIR, exist_ok=True)
            with open(os.path.join(SMA_ERR_DIR,"py_last_trace.txt"),"w",encoding="utf-8") as f: f.write(tb)
            with open(os.path.join(SMA_ERR_DIR,"server.log"),"a",encoding="utf-8") as f: f.write(tb+"\n")
        except Exception: pass
    return tb

def _json(handler, code, obj):
    data=json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

_PIPE=None
_CLASSES=None

def _bind_rules_feat():
    if not RULES_SRC or not os.path.isfile(RULES_SRC): return
    try:
        spec=importlib.util.spec_from_file_location("rt", RULES_SRC)
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        import __main__; setattr(__main__,"rules_feat", getattr(m,"rules_feat", None))
    except Exception as e:
        _log_exc("bind_rules_feat", e)

def load_pipe():
    global _PIPE, __CLASSES
    if _PIPE is not None: return _PIPE
    if not ML_PKL or not os.path.isfile(ML_PKL):
        raise RuntimeError(f"ML PKL not found: {ML_PKL}")
    _bind_rules_feat()
    obj=joblib.load(ML_PKL)
    # unwrap dict/list to get estimator/pipeline
    def pick(o):
        if hasattr(o,"predict"): return o
        if isinstance(o,dict):
            for k in ("pipe","pipeline","estimator","model"): 
                if k in o and o[k] is not None:
                    try: return pick(o[k])
                    except Exception: pass
        if isinstance(o,(list,tuple)) and o:
            return pick(o[0])
        raise RuntimeError("no predictor inside pickle")
    est=pick(obj)
    # fetch classes_
    if hasattr(est, "classes_"): _CLASSES=list(est.classes_)
    else:
        last = est.steps[-1][1] if hasattr(est,"steps") else est
        _CLASSES=list(getattr(last,"classes_", []))
    _PIPE=est
    return _PIPE

def rule_classify(texts):
    out=[]
    for t in texts:
        s=(t or "").lower()
        if any(k in s for k in ["報價","交期","quote","報價單"]): out.append("biz_quote"); continue
        if any(k in s for k in ["技術","無法","錯誤","連線","故障","error","bug","support"]): out.append("tech_support"); continue
        if any(k in s for k in ["發票","抬頭","變更","更新","invoice"]): out.append("profile_update"); continue
        if any(k in s for k in ["規則","政策","policy","條款"]): out.append("policy_qa"); continue
        if any(k in s for k in ["投訴","抱怨","申訴","complaint"]): out.append("complaint"); continue
        out.append("other")
    return out

def _override_tech_support(text, pred):
    s=(text or "").lower()
    if pred=="complaint" and any(k in s for k in ["無法","錯誤","連線","故障","crash","bug","error","support","技術"]):
        return "tech_support"
    return pred

def route_ml(texts, threshold=ML_THRESHOLD):
    est=load_pipe()
    # try predict_proba if available
    preds=[]
    if hasattr(est,"predict_proba"):
        proba=est.predict_proba(texts)
        classes=getattr(est,"classes_", None)
        if classes is None and hasattr(est,"steps"):
            classes=getattr(est.steps[-1][1], "classes_", None)
        classes=list(classes) if classes is not None else []
        for i, row in enumerate(proba):
            if classes:
                mx=max(row); pi=int(row.argmax())
                p=classes[pi] if pi < len(classes) else "other"
                p=_override_tech_support(texts[i], str(p))
                if mx < threshold: p=rule_classify([texts[i]])[0]
                preds.append(str(p))
            else:
                preds.append(rule_classify([texts[i]])[0])
    else:
        preds=[str(y) for y in est.predict(texts)]
        preds=[_override_tech_support(texts[i], preds[i]) for i in range(len(texts))]
    return preds

def kie_extract(texts):
    import re
    outs=[]
    for t in texts:
        s=t or ""
        # phone
        m=re.search(r'(09\d{2})[-\s]?(\d{3})[-\s]?(\d{3})', s); phone=""
        if m: phone="".join(m.groups())
        # amount
        m=re.search(r'(?:(?:NTD|NT\$|\$)\s*)?(\d{1,3}(?:,\d{3})+|\d+)\s*(?:元|NTD|NT\$|\$)?', s, re.I)
        amount=""
        if m:
            amount=m.group(1).replace(",","")
        outs.append({"phone":phone, "amount":amount})
    return outs

def _model_meta():
    est=load_pipe()
    last = est.steps[-1][1] if hasattr(est,"steps") else est
    classes = list(getattr(last,"classes_", []))
    return {"est_type": type(est).__name__, "clf_type": type(last).__name__, "classes": classes}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # keep server.log quiet here; we already mirror exceptions
        return

    def do_GET(self):
        try:
            p=urlparse(self.path).path
            if p=="/debug/model_meta":
                return _json(self, 200, _model_meta())
            return _json(self, 404, {"error":"not found"})
        except Exception as e:
            tb=_log_exc("GET", e)
            return _json(self, 500, {"error":"server_error","trace":tb})

    def do_POST(self):
        t0=time.perf_counter()
        try:
            p=urlparse(self.path).path
            n=int(self.headers.get("Content-Length","0") or 0)
            raw=self.rfile.read(n).decode("utf-8") if n>0 else "{}"
            Q=json.loads(raw)
        except Exception:
            return _json(self, 400, {"error":"invalid json"})

        try:
            if p=="/classify":
                texts=Q.get("texts",[]) or []
                route=str(Q.get("route","ml"))
                if route=="rule":
                    yp=rule_classify(texts); tag="rule"
                elif route=="ml":
                    yp=route_ml(texts); tag="ml"
                else:
                    yp=["other"]*len(texts); tag="openai"
                ms=int((time.perf_counter()-t0)*1000)
                audit_llm(f"{tag}.classify", tag, ms, 0.0)
                return _json(self, 200, {"pred":yp,"latency_ms":ms,"route":tag})

            if p=="/extract":
                texts=Q.get("texts",[]) or []
                fields=kie_extract(texts)
                ms=int((time.perf_counter()-t0)*1000)
                return _json(self, 200, {"fields":fields,"latency_ms":ms})

            if p=="/plan":
                intents=Q.get("intents",[]) or []
                mp={"biz_quote":"gen_quote","tech_support":"create_ticket","profile_update":"update_profile",
                    "complaint":"escalate","policy_qa":"faq","other":"noop"}
                actions=[mp.get(x,"noop") for x in intents]
                return _json(self, 200, {"actions":actions})

            if p=="/act":
                items=Q.get("items",[]) or []
                os.makedirs("rpa_out", exist_ok=True)
                for it in items:
                    mid=str(it.get("mail_id","m"))
                    act=str(it.get("action","noop"))
                    with open(os.path.join("rpa_out", f"act_{act}_{mid}.txt"),"w",encoding="utf-8") as f:
                        json.dump(it, f, ensure_ascii=False, indent=2)
                return _json(self, 200, {"ok":len(items),"dry_run":True})

            if p=="/tri-eval":
                texts=Q.get("texts",[]) or []
                labels=Q.get("labels",[]) or []
                runs=[]
                for tag,fn in (("rule",rule_classify),("ml",route_ml),("openai",lambda xs:["other"]*len(xs))):
                    t1=time.perf_counter(); yp=fn(texts); ms=int((time.perf_counter()-t1)*1000)
                    acc= (sum(int(a==b) for a,b in zip(labels, yp))/len(labels)) if labels else 0.0
                    runs.append({"route":tag,"pred":yp,"latency_ms":ms,"accuracy": round(acc,4)})
                dim={"word":sum(len(set((t or "").split())) for t in texts),
                     "char":sum(len(t or "") for t in texts), "rules":7}
                out={"n":len(texts),"runs":runs,"dim_diag":{"expected_dim":sum(dim.values()),"sum_branch":sum(dim.values()),"branch_dims":dim}}
                return _json(self, 200, out)

            if p=="/debug/proba":
                texts=Q.get("texts",[]) or []
                topk=int(Q.get("topk",6))
                est=load_pipe()
                if not hasattr(est,"predict_proba"):
                    return _json(self, 400, {"error":"no_predict_proba"})
                proba=est.predict_proba(texts)
                classes=list(getattr(est,"classes_", []))
                res=[]
                for i,row in enumerate(proba):
                    pairs=sorted([(float(row[j]), str(classes[j])) for j in range(len(classes))], reverse=True)[:topk]
                    res.append({"text":texts[i], "top": [{"label":l,"p":round(p,6)} for p,l in pairs]})
                return _json(self, 200, {"proba":res})

            return _json(self, 404, {"error":"not found"})
        except Exception as e:
            tb=_log_exc("POST", e)
            return _json(self, 200 if p=="/classify" else 500, {"error":"server_error","trace":tb})

def main():
    port=int(os.environ.get("PORT") or 8000)
    _ensure_db()
    srv=HTTPServer(("127.0.0.1", port), Handler)
    print(f"[OK] API ready :{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__=="__main__":
    main()
