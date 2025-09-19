#!/usr/bin/env python3
import argparse, joblib, sys
from pathlib import Path
import numpy as np
try:
    from scipy import sparse as sp
except Exception as e:
    print("[FATAL] SciPy not installed. pip install scipy", file=sys.stderr); raise

from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

class RightPad:
    def __init__(self, n_missing: int):
        self.n_missing = int(n_missing)
    def fit(self, X, y=None):
        return self
    def transform(self, X):
        if self.n_missing <= 0:
            return X
        n = X.shape[0]
        Z = sp.csr_matrix((n, self.n_missing), dtype=getattr(X, "dtype", np.float64))
        return sp.hstack([X, Z], format="csr")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp",  required=True, help="path to original intent_pro_cal.pkl")
    ap.add_argument("--out", dest="outp", required=True, help="path to write padded model")
    args = ap.parse_args()

    mpath = Path(args.inp)
    opath = Path(args.outp)

    pipe = joblib.load(mpath)
    assert isinstance(pipe, Pipeline), "[INTENT] not a sklearn Pipeline"

    # 找最後的 CalibratedClassifierCV
    last = pipe.steps[-1][1]
    if not isinstance(last, CalibratedClassifierCV):
        raise SystemExit("[INTENT] last step is not CalibratedClassifierCV")

    # 分類器期望寬度
    exp = int(last.calibrated_classifiers_[0].estimator.coef_.shape[1])

    # 先把前處理跑一次（用 1 條假資料即可）取得目前寬度
    pre = Pipeline(pipe.steps[:-1]) if len(pipe.steps) > 1 else None
    try:
        Xt = pre.transform(["dummy text"]) if pre else np.zeros((1, exp))
        cur = int(Xt.shape[1])
    except Exception as e:
        # 有些 pipeline 會同時需要 subject/body 拼接，給兩條也無妨
        Xt = pre.transform(["dummy", "text"]) if pre else np.zeros((2, exp))
        cur = int(Xt.shape[1])

    delta = exp - cur
    if delta < 0:
        raise SystemExit(f"[INTENT] current features {cur} > expected {exp} (cannot shrink)")
    if delta == 0:
        # 直接複製一份到 out，避免覆蓋你的原始檔
        joblib.dump(pipe, opath)
        print(f"[INTENT] already aligned: {cur} == {exp}. wrote -> {opath}")
        return

    # 在倒數第 1 個步驟前插入 RightPad
    pipe.steps.insert(-1, ("_rightpad_fix", RightPad(delta)))
    pipe = Pipeline(pipe.steps)
    # 驗證一下
    Xt2 = Pipeline(pipe.steps[:-1]).transform(["dummy text"])
    assert Xt2.shape[1] == exp, f"after pad got {Xt2.shape[1]} but expect {exp}"

    joblib.dump(pipe, opath)
    print(f"[INTENT] padded: {cur} -> {exp} (+{delta}) cols. wrote -> {opath}")

if __name__ == "__main__":
    main()
