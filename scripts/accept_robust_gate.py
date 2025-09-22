#!/usr/bin/env python3
import os, json, sys
from pathlib import Path

robust_json = Path(os.getenv("ROBUST_JSON", "reports_auto/pro/latest/robust_ab_url.json"))
try:
    data = json.loads(robust_json.read_text("utf-8"))
except Exception as e:
    print(json.dumps({"pass": False, "error": f"read {robust_json}: {e}"}, ensure_ascii=False))
    sys.exit(2)

def _b(v): return str(v).lower() in ("1","true","yes","y","on")

use_pre_int  = _b(os.getenv("ROBUST_USE_PREPROC_INTENT","0"))
use_pre_spam = _b(os.getenv("ROBUST_USE_PREPROC_SPAM","0"))

def _limit(name, default):
    v = os.getenv(f"GATE_MAX_URL_DROP_{name.upper()}")
    if v is None:
        v = os.getenv(f"MAX_URL_DROP_{name.upper()}")
    try:
        return float(v) if v is not None else default
    except:
        return default

intent_max = _limit("intent", 0.6)
spam_max   = _limit("spam",   0.6)

def _get(d, path, default=0.0):
    cur = d
    for k in path:
        if k not in cur: return default
        cur = cur[k]
    return cur

# intent 用 macro_f1、spam 用 accuracy
intent_base = float(_get(data, ["intent","baseline","metrics","macro_f1"]))
intent_variant = "url_with_pre" if use_pre_int else "url_no_pre"
intent_url  = float(_get(data, ["intent", intent_variant, "metrics", "macro_f1"]))
intent_drop = intent_base - intent_url

spam_base = float(_get(data, ["spam","baseline","metrics","accuracy"]))
spam_variant = "url_with_pre" if use_pre_spam else "url_no_pre"
spam_url  = float(_get(data, ["spam", spam_variant, "metrics", "accuracy"]))
spam_drop = spam_base - spam_url

ok = (intent_drop <= intent_max) and (spam_drop <= spam_max)
print(json.dumps({
  "pass": ok,
  "url_drop": {"intent": intent_drop, "spam": spam_drop},
  "limits": {"intent_max": intent_max, "spam_max": spam_max},
  "use_pre": {"intent": use_pre_int, "spam": use_pre_spam},
  "variants": {"intent": intent_variant, "spam": spam_variant}
}, ensure_ascii=False, indent=2))
sys.exit(0 if ok else 2)
