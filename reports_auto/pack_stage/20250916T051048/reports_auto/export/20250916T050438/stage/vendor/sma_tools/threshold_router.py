from __future__ import annotations
import os, json, re
from pathlib import Path
import numpy as np
from scipy import sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin

def _load_names():
    # 優先讀 reports 列出的候選；其次 intent/** 直掃
    base = Path.cwd()
    cand_lists = [
        base / "reports_auto" / "intent_import",  # 最新一輪下的清單
    ]
    json_paths = []
    for d in cand_lists:
        if d.exists():
            for sub in sorted(d.glob("*/rules_json_candidates.txt"))[::-1]:
                try:
                    json_paths += [Path(x.strip()) for x in sub.read_text().splitlines() if x.strip()]
                except: pass
    if not json_paths:
        for p in base.glob("intent/**/*"):
            s=str(p).lower()
            if p.suffix==".json" and any(k in s for k in ("rule","rules","threshold","router","names","vocab")):
                json_paths.append(p)

    # 從多個 JSON 嘗試抓 names/vocab
    for p in json_paths:
        try:
            obj=json.loads(Path(p).read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                for k in ("names","vocab","features","feature_names","columns"):
                    if k in obj and isinstance(obj[k], (list,tuple)) and obj[k]:
                        return [str(x) for x in obj[k]]
            if isinstance(obj, list) and obj and isinstance(obj[0], (str,int)):
                return [str(x) for x in obj]
        except: pass
    return None

class ThresholdRouter(BaseEstimator, TransformerMixin):
    """將規則字典/列表轉成固定長度稀疏向量。"""
    def __init__(self, feature_names=None):
        self.feature_names = list(feature_names) if feature_names else None

    def fit(self, X, y=None):
        if self.feature_names is None:
            names = _load_names()
            if names:
                self.feature_names = list(names)
            else:
                # 找不到就退回一個小向量，避免崩潰（會影響準度）
                self.feature_names = [f"feat_{i}" for i in range(7)]
        return self

    def transform(self, X):
        n=len(X); m=len(self.feature_names or [])
        M = sp.lil_matrix((n,m), dtype=np.float64)
        # 支援：每筆是 dict 或 list/tuple 或單值
        for i,xi in enumerate(X):
            if isinstance(xi, dict):
                for j,name in enumerate(self.feature_names):
                    v = xi.get(name, 0.0)
                    try: v=float(v)
                    except: v=0.0
                    if v: M[i,j]=v
            elif isinstance(xi, (list,tuple)):
                for j,name in enumerate(self.feature_names):
                    if j < len(xi):
                        try: v=float(xi[j])
                        except: v=0.0
                        if v: M[i,j]=v
            else:
                # 單值 → 放第一維
                try: v=float(xi)
                except: v=0.0
                if m>0 and v: M[i,0]=v
        return M.tocsr()
