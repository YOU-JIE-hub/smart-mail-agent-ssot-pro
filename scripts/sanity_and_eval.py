import os, json, pathlib, sys, time
from typing import Optional, List, Dict
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# 讓 pickle 裡的 vendor.rules_features 可以被 import 到
sys.path.append(str(Path("vendor").resolve()))
try:
    from rules_features import rules_feat  # noqa: F401
except Exception:
    pass

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score, average_precision_score

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT/".env.local"
PATHS = ROOT/"configs/data_contracts/paths.json"
OUTDIR = ROOT/"reports_auto/eval_snapshots"
OUTDIR.mkdir(parents=True, exist_ok=True)

def _load_env(fp: Path) -> Dict[str,str]:
    out={}
    if not fp.exists(): return out
    for ln in fp.read_text(encoding="utf-8").splitlines():
        ln=ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln: continue
        k,v = ln.split("=",1)
        out[k.strip()] = v.strip()
    return out

def _load_json(fp: Path) -> dict:
    return json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}

env = _load_env(ENV)
paths = _load_json(PATHS)

def _must(p):
    if not p or not Path(p).exists():
        raise FileNotFoundError(p)
    return str(p)

def read_jsonl(fp: str, text_key="text", label_key="label"):
    rows=[]
    with open(fp,"r",encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            j=json.loads(ln)
            t=j.get(text_key) or j.get("content") or j.get("body") or ""
            y=j.get(label) if (label_key in (label:="label",)) else (j.get("y") or j.get("target"))
            # 盡量容錯：label 可能在 'label' 或 'y' 或 'target'
            y=j.get(label_key, y)
            rows.append({"text": str(t), "label": y})
    return pd.DataFrame(rows)

def safe_report(y_true, y_pred, y_score=None):
    rep = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    out = {
        "acc": float(accuracy_score(y_true, y_pred)),
        "report": rep
    }
    # 嘗試算 ROC/AUPRC（二分類時）
    uniq = sorted(set(y_true))
    if len(uniq)==2 and y_score is not None:
        try:
            # 將 y_true 映射成 {positive:1, other:0}
            pos = uniq[-1]
            y_bin = [1 if y==pos else 0 for y in y_true]
            out["roc_auc"] = float(roc_auc_score(y_bin, y_score))
            out["auprc"]   = float(average_precision_score(y_bin, y_score))
        except Exception:
            pass
    return out

snap = {"ts": time.strftime("%Y%m%dT%H%M%S"), "env": env, "paths": paths, "results": {}}

# ===== Intent =====
intent_pkl = env.get("SMA_INTENT_PRO_CAL") or (paths.get("intent_pro_cal",{}) or {}).get("path")
if intent_pkl and Path(intent_pkl).exists():
    m = joblib.load(intent_pkl)
    snap["results"]["intent_meta"] = {
        "type": type(m).__name__,
        "has_predict": hasattr(m,"predict"),
        "has_predict_proba": hasattr(m,"predict_proba"),
        "attrs": [a for a in ("classes_","n_features_in_") if hasattr(m,a)]
    }
    # 取資料
    intent_data = env.get("SMA_INTENT_DATA") or (paths.get("intent_data_merged",{}) or {}).get("path") \
                  or (paths.get("intent_data_full",{}) or {}).get("path")
    if intent_data and Path(intent_data).exists():
        df = read_jsonl(intent_data)
        df = df.dropna(subset=["text","label"])
        df_s = df.sample(min(2000, len(df)), random_state=42) if len(df)>2000 else df
        y_pred = m.predict(df_s["text"].tolist())
        y_score = None
        if hasattr(m,"predict_proba"):
            try:
                proba = m.predict_proba(df_s["text"].tolist())
                # 取最大類別機率
                y_score = proba.max(axis=1)
            except Exception:
                pass
        snap["results"]["intent_eval"] = safe_report(df_s["label"].tolist(), y_pred, y_score)
        snap["results"]["intent_head"] = Counter(y_pred).most_common(10)
else:
    snap["results"]["intent_meta"] = {"error":"intent pickle not found"}

# ===== Spam =====
spam_pipe = env.get("SMA_SPAM_PIPELINE") or (paths.get("spam_model_pipeline",{}) or {}).get("path")
spam_text = env.get("SMA_SPAM_TEXT_MODEL") or (paths.get("spam_text_model",{}) or {}).get("path")
spam_thr  = env.get("SMA_SPAM_THR") or (paths.get("spam_ens_thresholds",{}) or {}).get("path")

spam_model_path = spam_pipe or spam_text  # 先管線，沒有就單模型
if spam_model_path and Path(spam_model_path).exists():
    sm = joblib.load(spam_model_path)
    snap["results"]["spam_meta"] = {
        "type": type(sm).__name__,
        "has_predict": hasattr(sm,"predict"),
        "has_predict_proba": hasattr(sm,"predict_proba"),
    }
    # 資料優先用 spam_sa，其次 spam、再 trec
    def pick(*keys):
        for k in keys:
            p=(paths.get(k,{}) or {}).get("path")
            if p and Path(p).exists(): return p
        return None
    spam_train = pick("spam_sa_train","spam_train","trec_train")
    if spam_train:
        df = read_jsonl(spam_train)
        df = df.dropna(subset=["text","label"])
        df_s = df.sample(min(2000, len(df)), random_state=42) if len(df)>2000 else df
        y_pred = sm.predict(df_s["text"].tolist())
        y_score = None
        if hasattr(sm,"predict_proba"):
            try:
                y_score = sm.predict_proba(df_s["text"].tolist())[:,1]
            except Exception:
                pass
        snap["results"]["spam_eval"] = safe_report(df_s["label"].tolist(), y_pred, y_score)
        snap["results"]["spam_head"] = Counter(y_pred).most_common(10)
else:
    snap["results"]["spam_meta"] = {"error":"spam model not found"}

# ===== KIE（不在這裡重跑模型，先做資產健檢）=====
kie_dir = env.get("SMA_KIE_DIR") or (paths.get("kie_model_dir",{}) or {}).get("path")
if kie_dir:
    need = ["config.json","model.safetensors","tokenizer.json"]
    exist = {n: Path(kie_dir, n).exists() for n in need}
    snap["results"]["kie_assets"] = {"dir": kie_dir, "exists": exist}
else:
    snap["results"]["kie_assets"] = {"error":"kie dir not found"}

# 寫檔
out = OUTDIR/f"eval_snapshot_{snap['ts']}.json"
out.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] wrote {out}")
