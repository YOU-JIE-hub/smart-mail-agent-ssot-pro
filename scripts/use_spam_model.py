from __future__ import annotations
import os, sys, json, types, argparse, pathlib, joblib

def unc_to_wsl(p: str) -> str:
    # 把 \\wsl.localhost\Ubuntu-22.04\home\youjie\... 轉成 /home/youjie/...
    tag = r"\\wsl.localhost\Ubuntu-22.04\\"
    if p.startswith(tag):
        return "/" + p.split(tag,1)[1].replace("\\","/")
    return p

def add_shims():
    # 某些舊 pkl 需要這些符號存在於 __main__
    m = sys.modules.setdefault("__main__", types.ModuleType("__main__"))
    for name in ("rules_feat","rules_feat_func","rules_features","feat_rules"):
        if not hasattr(m, name):
            setattr(m, name, (lambda x: {}))

def inspect_pipeline(pipe):
    info = {"type": type(pipe).__name__, "has_predict": hasattr(pipe, "predict"), "classes": None, "steps": []}
    # 嘗試抓 classes_
    if hasattr(pipe, "classes_"):
        info["classes"] = list(getattr(pipe, "classes_"))
    # 抓最後一層估計器
    final = None
    if hasattr(pipe, "steps"):
        info["steps"] = [name for name,_ in pipe.steps]
        final = pipe.steps[-1][1]
    elif hasattr(pipe, "_final_estimator"):
        final = getattr(pipe, "_final_estimator")
    if info["classes"] is None and final is not None and hasattr(final, "classes_"):
        info["classes"] = list(getattr(final, "classes_"))
    info["has_proba"] = hasattr(pipe, "predict_proba") or (final is not None and hasattr(final, "predict_proba"))
    return info

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="spam model .pkl (UNC 或 WSL 路徑皆可)")
    args = ap.parse_args()

    p_raw = args.model
    p = unc_to_wsl(p_raw)
    if not pathlib.Path(p).exists():
        sys.stderr.write(f"[FATAL] 模型檔不存在: {p_raw} → {p}\n")
        sys.exit(2)

    add_shims()
    model = joblib.load(p)

    info = inspect_pipeline(model)
    print(json.dumps({"model": p, "info": info}, ensure_ascii=False, indent=2))

    # 寫出 ENV（只覆寫 SPAM_PKL）
    outdir = pathlib.Path("reports_auto") / ("resolve_SPAM_" + __import__("datetime").datetime.now().strftime("%Y%m%dT%H%M%S"))
    outdir.mkdir(parents=True, exist_ok=True)
    env_fp = outdir / "MODEL_PATHS.auto.env"
    with env_fp.open("w", encoding="utf-8") as f:
        f.write(f'SPAM_PKL="{p}"\n')
    print("ENV =>", env_fp.as_posix())

    # 煙霧測試（不要求準確，只驗可推論）
    try:
        preds = model.predict(["需要維修幫我看一下", "我要報價單", "資料需要修改", "這是什麼規則?"])
        print("smoke_pred:", [str(x) for x in preds])
    except Exception as e:
        sys.stderr.write(f"[WARN] 煙霧測試失敗: {e}\n")

if __name__ == "__main__":
    main()
