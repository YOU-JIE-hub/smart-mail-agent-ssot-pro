import os, sys, joblib, types, json, traceback
from pathlib import Path
from sma.features.intent_rules import rules_feat as stable_rules_feat

def main(src, dst):
    # 讓 joblib 在還原時能找到 __main__.rules_feat
    fake_main = types.ModuleType("__main__")
    fake_main.rules_feat = stable_rules_feat
    sys.modules["__main__"] = fake_main

    pipe = joblib.load(src)
    # 找 pipeline 裡的 FunctionTransformer 並換函數指標
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import FunctionTransformer

    def replace_rules(obj):
        if isinstance(obj, Pipeline):
            for name, step in obj.steps:
                if isinstance(step, FunctionTransformer):
                    step.func = stable_rules_feat
                else:
                    replace_rules(step)
        elif isinstance(obj, ColumnTransformer):
            new_trans = []
            for name, trans, cols in obj.transformers:
                if isinstance(trans, FunctionTransformer):
                    trans.func = stable_rules_feat
                    new_trans.append((name, trans, cols))
                else:
                    replace_rules(trans)
                    new_trans.append((name, trans, cols))
            obj.transformers = new_trans

    replace_rules(pipe)

    # 自檢：跑一筆，檢查維度與 classes_
    meta = {
        "classes_": getattr(pipe, "classes_", None),
        "n_features_in_": getattr(getattr(pipe, "steps", [("",None)])[-1][1], "n_features_in_", None)
    }
    try:
        _ = pipe.predict_proba(["測試文字"])
        meta["smoke_predict_proba"] = True
    except Exception as e:
        meta["smoke_predict_proba"] = f"ERROR: {type(e).__name__}: {e}"

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, dst)
    print(json.dumps({"src":src, "dst":dst, "meta":meta}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    a = ap.parse_args()
    main(a.src, a.dst)
