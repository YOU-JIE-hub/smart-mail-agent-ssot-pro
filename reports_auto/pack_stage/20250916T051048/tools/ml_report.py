
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict

from tools.ml_compat import alias_main, joblib_load
alias_main()

def _compose(e:dict)->str:
    return (e.get("subject","")+"\n"+e.get("body","")).strip()

def _load_label_map()->Dict[str,str]:
    p = Path("configs/intent_label_map.json")
    if p.exists():
        m = json.loads(p.read_text(encoding="utf-8"))
        return {str(k): str(v) for k,v in m.items()}
    return {}

def main():
    ts = time.strftime("%Y%m%dT%H%M%S")
    outdir = Path(f"reports_auto/eval/{ts}")
    outdir.mkdir(parents=True, exist_ok=True)
    report = {"ts": ts}

    mp  = _load_label_map()
    obj = joblib_load("artifacts/intent_pro_cal.pkl")
    est = obj
    if isinstance(obj, dict):
        for k in ("pipeline","model","clf","estimator","sk_model","pipe"):
            v = obj.get(k)
            if hasattr(v,"predict"): est = v; break

    cls_raw = [str(c) for c in getattr(est,"classes_",[])]
    cls_zh  = [mp.get(c,c) for c in cls_raw]
    report["classes_raw"] = cls_raw
    report["classes_zh"]  = cls_zh
    report["label_map"]   = mp

    # 測資：fixtures 或內建六筆
    X = []
    fj = Path("fixtures/eval_set.jsonl")
    if fj.exists():
        for ln in fj.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(ln); e = o.get("email",{})
                X.append({"gold": o.get("intent",""), "text": _compose(e)})
            except Exception:
                pass
    if not X:
        X = [
          {"gold":"一般回覆", "text":"[一般回覆] 測試\nhello"},
          {"gold":"報價",   "text":"報價 請提供 單價:100 數量:2"},
          {"gold":"投訴",   "text":"投訴\n客訴"},
          {"gold":"技術支援","text":"技術支援 ticket:TS-1234"},
          {"gold":"規則詢問","text":"請問規則\n這是規則詢問"},
          {"gold":"資料異動","text":"修改我的地址\n新的地址在…"},
        ]

    raw = [str(x) for x in est.predict([r["text"] for r in X])]
    # 簡單信心值
    conf = [0.0]*len(raw)
    try:
        if hasattr(est,"predict_proba"):
            import numpy as np
            P = est.predict_proba([r["text"] for r in X])
            idx = [list(getattr(est,"classes_",[])).index(y) for y in raw]
            conf = [float(P[i,j]) for i,j in enumerate(idx)]
    except Exception:
        pass

    preds=[]
    for i,r in enumerate(X):
        zh = mp.get(raw[i], raw[i])
        preds.append({"gold": r["gold"], "pred_raw": raw[i], "pred_zh": zh, "conf": conf[i]})
    report["preds"] = preds

    Path(outdir/"ml_model_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"[ML-REPORT] {outdir}/ml_model_report.json")

if __name__ == "__main__":
    main()
