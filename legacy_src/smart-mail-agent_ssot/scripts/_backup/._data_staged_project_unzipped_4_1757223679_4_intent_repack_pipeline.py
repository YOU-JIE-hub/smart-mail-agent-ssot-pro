#!/usr/bin/env python3
# 檔案位置：.sma_tools/intent_repack_pipeline.py
# 模組用途：從 artifacts/intent_pro_cal.pkl 抽出 vectorizer 與 CalibratedClassifierCV，
#           以 TextRules6Featurizer(含 6 維規則 + 寬度補齊) 重建標準 Pipeline，輸出 *_fixed.pkl
from __future__ import annotations
import argparse, joblib
from pathlib import Path
from typing import Any, Tuple
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

# 依賴本專案可序列化 Transformer
from smart_mail_agent.ml.rules6_padder import TextRules6Featurizer

def _first_pipeline(obj: Any) -> Pipeline | None:
    if isinstance(obj, Pipeline):
        return obj
    if isinstance(obj, dict):
        for k in ("pipe","pipeline","model"):
            v = obj.get(k)
            if isinstance(v, Pipeline):
                return v
    if isinstance(obj, (list, tuple)):
        for v in obj:
            if isinstance(v, Pipeline):
                return v
    return None

def _extract_vect_and_clf(obj: Any) -> Tuple[Any, CalibratedClassifierCV]:
    p = _first_pipeline(obj)
    if p is not None:
        vect = p[:-1] if len(p.steps) >= 2 else p
        clf  = p.steps[-1][1]
        if isinstance(clf, CalibratedClassifierCV):
            return vect, clf
    if isinstance(obj, dict):
        v = obj.get("vect") or obj.get("vectorizer")
        c = obj.get("cal")  or obj.get("classifier") or obj.get("clf") or obj.get("model")
        if v is not None and isinstance(c, CalibratedClassifierCV):
            return v, c
    if isinstance(obj, CalibratedClassifierCV):
        raise SystemExit("[FATAL] 權重僅含 CalibratedClassifierCV，缺少向量器。")
    raise SystemExit(f"[FATAL] 無法抽出 (vectorizer, CalibratedClassifierCV)。type={type(obj)}")

def _expected_n_features(clf: CalibratedClassifierCV) -> int:
    # sklearn 1.7.x：CalibratedClassifierCV.calibrated_classifiers_[i].estimator.coef_
    for cc in clf.calibrated_classifiers_:
        est = getattr(cc, "estimator", None)
        if est is not None and hasattr(est, "coef_"):
            return int(est.coef_.shape[1])
    raise SystemExit("[FATAL] 找不到底層 estimator.coef_ 以推導期望特徵寬度。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="artifacts/intent_pro_cal.pkl")
    ap.add_argument("--out", dest="dst", default="artifacts/intent_pro_cal_fixed.pkl")
    ap.add_argument("--overwrite", action="store_true", help="覆蓋輸入檔（將先備份為 .bak）")
    args = ap.parse_args()

    src = Path(args.src); dst = Path(args.dst)
    obj = joblib.load(src)
    vect, clf = _extract_vect_and_clf(obj)
    need = _expected_n_features(clf)

    feat = TextRules6Featurizer(vectorizer=vect, expected_n_features=need)
    pipe = Pipeline([("feat", feat), ("cal", clf)])

    # 照慣例輸出到 *_fixed.pkl
    dst.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, dst)
    print(f"[OK] wrote fixed pipeline => {dst}")

    if args.overwrite:
        bak = src.with_suffix(src.suffix + f".bak.{__import__('datetime').datetime.now().strftime('%Y%m%dT%H%M%S')}")
        src.rename(bak)
        dst.rename(src)
        print(f"[OK] backup => {bak}")
        print(f"[OK] replaced original => {src}")

if __name__ == "__main__":
    main()
