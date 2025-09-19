from __future__ import annotations

import json
import os
import pickle
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import joblib

ROOT = Path(os.environ.get("SMA_ROOT", Path(__file__).resolve().parents[3]))
DB = ROOT / "reports_auto" / "audit.sqlite3"
STORE = ROOT / "reports_auto" / "artifacts_store"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _pick_model_file(folder: Path) -> Path | None:
    cand = []
    cand += list(folder.glob("**/*model*.joblib"))
    cand += list(folder.glob("**/*model*.pkl"))
    cand += list(folder.glob("**/*.joblib"))
    cand += list(folder.glob("**/*.pkl"))
    return cand[0] if cand else None


def _load_sklearn(fp: Path):
    try:
        return joblib.load(fp)
    except Exception:
        with open(fp, "rb") as f:
            return pickle.load(f)


def _load_rules(folder: Path) -> dict[str, Any]:
    for name in ("kie_rules.json", "rules.json"):
        p = folder / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _ensure_model(kind: str) -> tuple[str, dict[str, Any]]:
    # 以資料夾名含 kind 關鍵字為優先
    folders = [p for p in STORE.iterdir() if p.is_dir() and kind in p.name.lower()]
    if not folders:  # 次選：掃全部，憑檔名包含 kind
        for p in STORE.iterdir():
            if not p.is_dir():
                continue
            hits = list(p.glob(f"**/*{kind}*.pkl")) + list(p.glob(f"**/*{kind}*.joblib"))
            if hits:
                folders = [p]
                break
    if not folders:
        raise FileNotFoundError(f"model folder for kind={kind} not found under {STORE}")
    folder = folders[0]
    fp = _pick_model_file(folder)
    meta = {"folder": str(folder), "model_file": str(fp) if fp else None}
    return str(folder), meta


def _register(kind: str, meta: dict[str, Any]):
    conn = _conn()
    conn.execute(
        "INSERT INTO models(kind,version,path,meta,ts) VALUES(?,?,?,?,strftime('%s','now'))",
        (kind, meta.get("version", ""), meta.get("folder", ""), json.dumps(meta, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def _log(kind: str, mail_id: str, ok: bool, ms: int, details: dict[str, Any]):
    conn = _conn()
    conn.execute(
        """INSERT INTO inference_logs(ts,kind,mail_id,ok,latency_ms,details)
                    VALUES(strftime('%s','now'),?,?,?,?,?)""",
        (kind, mail_id, 1 if ok else 0, ms, json.dumps(details, ensure_ascii=False)),
    )
    # 同步寫 metrics
    conn.execute(
        """INSERT INTO metrics(ts,stage,duration_ms,ok,extra)
                    VALUES(strftime('%s','now'),?, ?, ?, ?)""",
        (f"model/{kind}", ms, 1 if ok else 0, json.dumps(details, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


# ------------ 推論 API ------------
def predict_spam(text: str, mail_id: str = "") -> dict[str, Any]:
    t0 = time.time()
    folder, meta = _ensure_model("spam")
    fp = Path(meta.get("model_file") or "")
    if not fp.exists():
        raise FileNotFoundError("spam model file not found")
    model = _load_sklearn(fp)
    if hasattr(model, "predict_proba"):
        proba = float(model.predict_proba([text])[0][1])
    else:
        # 二值模型但無 proba，退化為 0/1
        proba = float(model.predict([text])[0])
    label = "spam" if proba >= 0.5 else "ham"
    ms = int((time.time() - t0) * 1000)
    out = {"label": label, "proba": proba}
    _log("spam", mail_id, True, ms, {"proba": proba})
    return out


def predict_intent(text: str, mail_id: str = "") -> dict[str, Any]:
    t0 = time.time()
    folder, meta = _ensure_model("intent")
    fp = Path(meta.get("model_file") or "")
    if not fp.exists():
        raise FileNotFoundError("intent model file not found")
    model = _load_sklearn(fp)
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba([text])[0]
        classes = list(getattr(model, "classes_", [str(i) for i in range(len(probs))]))
        # 取前3
        pairs = sorted(zip(classes, probs, strict=False), key=lambda x: x[1], reverse=True)[:3]
        top = [{"label": c, "proba": float(p)} for c, p in pairs]
        label = top[0]["label"]
    else:
        label = str(model.predict([text])[0])
        top = [{"label": label, "proba": 1.0}]
    ms = int((time.time() - t0) * 1000)
    out = {"label": label, "top": top}
    _log("intent", mail_id, True, ms, {"top": top})
    return out


_FALLBACK_FIELDS = [
    ("amount", r"(?i)\b(?:amount|total|sum)\s*[:=]?\s*\$?\s*([0-9.,]+)"),
    ("date", r"(?i)\b(?:date|issued|on)\s*[:=]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})"),
    ("po", r"(?i)\bPO[-\s]?#?\s*([A-Za-z0-9-]{4,})"),
]


def extract_kie(text: str, mail_id: str = "") -> dict[str, Any]:
    t0 = time.time()
    folder, meta = _ensure_model("kie")
    rules = _load_rules(Path(folder))
    fields = {}
    # 1) 規則優先
    for k, pat in rules.get("patterns", {}).items():
        m = re.search(pat, text, flags=re.I | re.M)
        if m:
            fields[k] = m.group(1) if m.groups() else m.group(0)
    # 2) 沒命中的基本回退
    for k, pat in _FALLBACK_FIELDS:
        if k not in fields:
            m = re.search(pat, text, flags=re.I | re.M)
            if m:
                fields[k] = m.group(1)
    ms = int((time.time() - t0) * 1000)
    out = {"fields": fields, "confidence": 0.75 if fields else 0.0}
    _log("kie", mail_id, True, ms, out)
    return out
