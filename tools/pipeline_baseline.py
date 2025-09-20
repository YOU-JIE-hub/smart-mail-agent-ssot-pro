from __future__ import annotations
import os, json, pathlib, hashlib
from typing import Any, Dict, Tuple, List, Optional

import joblib
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, f1_score

from vendor.rules_features import rules_feat, feature_schema_from_fitted

# ---- utils ----
def _exists(p: Optional[str]) -> bool:
    return bool(p and pathlib.Path(p).exists())

def _sha256_head(path: pathlib.Path, n: int = 1024*1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(n))
    return h.hexdigest()

# ---- public: load_model ----
def load_model(path: str | None, task: str) -> Tuple[Any, Dict]:
    """
    回傳 (model_or_pipeline, meta)
    - intent: 期望 Pipeline([('features', FeatureUnion), ('clf', CalibratedClassifierCV/LinearSVC/LogReg)])
    - spam  : 期望 Pipeline([('vec', TfidfVectorizer), ('clf', ...)])
    - kie   : 期望 HF 目錄，可 forward；這裡只負責存在性與最小載入（避免重吃顯存）
    """
    meta: Dict[str, Any] = {"task": task, "path": path, "status": "error"}

    if task in ("intent", "spam"):
        if not _exists(path):
            meta.update(error="path_missing")
            return None, meta
        p = pathlib.Path(path)
        meta["sha256_head"] = _sha256_head(p)
        obj = joblib.load(p)

        # 支援老格式 dict['pipeline'] 與直接 Pipeline
        if isinstance(obj, dict) and "pipeline" in obj:
            pipe = obj["pipeline"]
        else:
            pipe = obj

        if not hasattr(pipe, "predict"):
            meta.update(error="no_predict_on_loaded_object")
            return None, meta

        # ----- 任務特定校驗 -----
        if task == "intent":
            # 需要 features block；若沒有，嘗試修復；仍無 → 報錯
            try:
                steps = dict(pipe.steps)
            except Exception:
                meta.update(error="not_a_sklearn_pipeline")
                return None, meta

            if "features" not in steps:
                # 嘗試補：把 rules_feat 接上
                feat = rules_feat()
                # 猜測分類器名稱
                clf_name = next((k for k,_ in pipe.steps if k != "features"), "clf")
                clf = steps.get(clf_name)
                if clf is None:
                    meta.update(error="no_clf_found_to_rewire")
                    return None, meta
                pipe = Pipeline([("features", feat), (clf_name, clf)])

            # 若已 fit，可以取 n_features_in_
            try:
                nfin = getattr(dict(pipe.steps)["features"], "n_features_in_", None)
            except Exception:
                nfin = None
            meta.update(status="ok", is_pipeline=True, n_features=nfin)
            return pipe, meta

        elif task == "spam":
            # 如果不是 Pipeline（例如只有 LR），拒跑
            if not isinstance(pipe, Pipeline):
                meta.update(error="spam_model_not_pipeline_missing_vectorizer")
                return None, meta
            # 粗檢向量器
            try:
                _ = pipe.named_steps  # type: ignore
            except Exception:
                meta.update(error="spam_pipeline_has_no_steps")
                return None, meta
            meta.update(status="ok", is_pipeline=True)
            return pipe, meta

    elif task == "kie":
        # 只做存在性與檔案檢查，forward 交給 eval_kie
        d = pathlib.Path(path or "")
        if not d.exists():
            meta.update(error="dir_missing")
            return None, meta
        needed = ["config.json", "model.safetensors", "tokenizer.json"]
        flags = {k: (d / k).exists() for k in needed}
        meta.update(status="ok" if all(flags.values()) else "incomplete", ready_flags=flags)
        return str(d), meta

    meta.update(error="unsupported_task")
    return None, meta
