from pathlib import Path
import json, time, importlib, sys
# rule eval
def run_rule():
    from tools.tri_model_eval import out_dir as _; from tools.tri_model_eval import acc as __
    return Path(_).parent.name  # 只是觸發輸出，ID 無用

# ml eval
def run_ml():
    import tools.tri_model_eval_ml as M  # 會輸出 summary_ml.md
    return "ok"

# ml boosted eval
def run_ml_boost():
    import tools.tri_model_eval_ml_boosted as B  # 會輸出 acc 對照
    return "ok"

if __name__=="__main__":
    try:
        run_rule()
    except Exception: pass
    try:
        run_ml()
    except Exception: pass
    try:
        run_ml_boost()
    except Exception: pass
    print("[INTENT] done")
