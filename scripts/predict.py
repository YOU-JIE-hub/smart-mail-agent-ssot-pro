import os, sys, json, joblib, re, unicodedata
from pathlib import Path
from inspect import signature
from runtime_preproc import normalize_text  # 可能不支援 task=，下面會自動偵測

def _env_true(k, default='1'):
    v = os.environ.get(k, default)
    return str(v).lower() not in ('0','false','no','off','')

MODEL = os.environ.get("MODEL_PKL") or os.environ.get("INTENT_PKL") or os.environ.get("SPAM_PKL")
TASK  = (os.environ.get("TASK","intent") or "intent").lower()  # intent | spam

# task-specific defaults: intent 預設關，spam 預設開
if TASK == 'spam':
    USE_PRE = _env_true("ENABLE_PREPROC_SPAM", os.environ.get("ENABLE_PREPROC","1") or "1")
else:
    USE_PRE = _env_true("ENABLE_PREPROC_INTENT", os.environ.get("ENABLE_PREPROC","0") or "0")

if not MODEL or not Path(MODEL).exists():
    print("ERR: MODEL_PKL/INTENT_PKL/SPAM_PKL 未設定或檔案不存在", file=sys.stderr)
    sys.exit(2)

pipe = joblib.load(MODEL)

_URL_RE = re.compile(r'(https?://\S+|www\.\S+)', re.IGNORECASE)

def _preprocess(text: str, task: str, use_pre: bool):
    if not use_pre:
        return text
    # 若 normalize_text 支援 task= 參數，就用它
    try:
        if 'task' in signature(normalize_text).parameters:
            return normalize_text(text, task=task)
    except Exception:
        pass
    # 否則使用本地 fallback：intent 移除 URL、spam 轉成 <URL>
    s = str(text)
    s = unicodedata.normalize('NFKC', s)
    if task == 'spam':
        s = _URL_RE.sub(' <URL> ', s)
    else:
        s = _URL_RE.sub(' ', s)
    s = s.lower()
    s = s.replace('<url>', '<URL>')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _to_py(obj):
    try:
        import numpy as np
        if isinstance(obj, np.bool_): return bool(obj)
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
    except Exception:
        pass
    try:
        return obj.item()
    except Exception:
        return obj

def infer_one(text):
    t = _preprocess(text, TASK, USE_PRE)

    y = pipe.predict([t])[0]
    y = _to_py(y)
    out = {"task": TASK, "text": t, "pred": y}

    try:
        proba = pipe.predict_proba([t])[0]
        labels = getattr(pipe, "classes_", None)
        if labels is not None:
            labels = [str(l) for l in list(labels)]
            pairs = sorted(zip(labels, getattr(proba, "tolist", lambda: proba)()), key=lambda x: x[1], reverse=True)[:3]
            out["topk"] = [{"label": lbl, "p": float(p)} for lbl, p in pairs]
    except Exception:
        pass

    return out

if __name__ == "__main__":
    for ln in sys.stdin:
        ln = ln.strip()
        if not ln:
            continue
        print(json.dumps(infer_one(ln), ensure_ascii=False))
