#!/usr/bin/env python
import os, sys, json, argparse, joblib
from typing import Any, Dict

from sma.common.intent_compat import load_pipeline as intent_load
from sma.common.intent_compat import predict_intent as intent_predict
from sma.common.intent_compat import warmup as intent_warmup
from sma.common.intent_compat import meta as intent_meta, last_error as intent_last_err

def predict_spam(text: str) -> Dict[str, Any]:
    p = os.getenv("SPAM_PKL")
    if not p or not os.path.exists(p):
        return {"task":"spam","text":text,"error":f"missing SPAM_PKL at {p!r}","env":{"SPAM_PKL":p}}
    try:
        pipe = joblib.load(p)
        proba = pipe.predict_proba([text])[0]
        idx = int(proba.argmax())
        return {"task":"spam","text":text,"label":idx,"score":float(proba[idx]),"model":p}
    except Exception as e:
        return {"task":"spam","text":text,"error":f"{type(e).__name__}: {e}","model":p}

def predict_intent_cli(text: str) -> Dict[str, Any]:
    p = os.getenv("INTENT_PKL")
    if not p or not os.path.exists(p):
        return {"task":"intent","text":text,"error":f"missing INTENT_PKL at {p!r}","env":{"INTENT_PKL":p}}
    try:
        intent_load(p)
        try:
            intent_warmup(text or "warmup")
        except Exception:
            pass
        res = intent_predict(text)
        res.update({"task":"intent","text":text,"model":p,"meta":intent_meta()})
        return res
    except Exception as e:
        return {"task":"intent","text":text,"error":f"{type(e).__name__}: {e}","model":p,"last_error":intent_last_err()}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["spam","intent"], required=True)
    ap.add_argument("--text", required=True)
    args = ap.parse_args()
    if args.task == "spam":
        out = predict_spam(args.text)
    else:
        out = predict_intent_cli(args.text)
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
