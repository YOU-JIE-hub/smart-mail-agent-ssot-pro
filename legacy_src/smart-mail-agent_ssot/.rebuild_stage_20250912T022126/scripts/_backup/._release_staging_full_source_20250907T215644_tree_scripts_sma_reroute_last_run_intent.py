#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reroute intents on the latest E2E run with cases.jsonl:
- Load thresholds
- Load regex rules (configs/intent_rules.yml or built-in minimal set)
- Try to load artifacts/intent_pro_cal.pkl; inject __main__.rules_feat for legacy pickles
- Predict (or fallback to rules-only) then apply threshold+rules
- Always write:
  - intent_reroute_suggestion.ndjson
  - intent_reroute_audit.csv
  - intent_reroute_summary.md
- Errors go to reports_auto/errors/REROUTE_CRASH_<ts>/
"""
import sys, os, json, re, time, traceback
from pathlib import Path
from collections import Counter

TS = time.strftime("%Y%m%dT%H%M%S")
ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot").resolve()
ERRDIR = ROOT / f"reports_auto/errors/REROUTE_CRASH_{TS}"
ERRDIR.mkdir(parents=True, exist_ok=True)

def elog(name: str, msg: str, with_exc: bool=False):
    p = ERRDIR / name
    p.write_text(msg + ("\n\n" + traceback.format_exc() if with_exc else ""), encoding="utf-8")

def list_e2e_dirs():
    base = ROOT / "reports_auto" / "e2e_mail"
    if not base.exists(): return []
    ds = [p for p in base.iterdir() if p.is_dir() and re.match(r"^\\d{8}T\\d{6}$", p.name)]
    ds.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return ds

def load_thresholds():
    p = ROOT / "reports_auto" / "intent_thresholds.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            elog("threshold_read.log", f"bad thresholds file: {p}", with_exc=True)
    return {"其他":0.40,"報價":0.30,"技術支援":0.30,"投訴":0.30,"規則詢問":0.30,"資料異動":0.30}

def safe_text(rec: dict) -> str:
    for k in ("text","body","snippet","raw","html"):
        t = rec.get(k)
        if isinstance(t,str) and t.strip():
            return t
    s = rec.get("subject","")
    b = rec.get("body","")
    return (s + "\\n" + b).strip()

def inject_rules_feat_symbol():
    try:
        import __main__
        from smart_mail_agent.ml.rules_feat import rules_feat as _rf
        setattr(__main__, "rules_feat", _rf)
    except Exception:
        elog("inject_rules_feat.log", "failed to inject __main__.rules_feat", with_exc=True)

def load_intent_model():
    inject_rules_feat_symbol()
    model_p = ROOT / "artifacts" / "intent_pro_cal.pkl"
    try:
        import joblib

# --- inject_main_rules_feat: make legacy pickles work ---
import sys, types
from smart_mail_agent.ml.rules_feat import rules_feat as _rf
m = sys.modules.get("__main__") or types.ModuleType("__main__")
setattr(m, "rules_feat", _rf)
sys.modules["__main__"] = m
# -------------------------------------------------------

        return joblib.load(model_p)
    except Exception:
        elog("model_load_joblib.log", f"joblib.load failed: {model_p}", with_exc=True)
        try:
            import pickle
            with open(model_p, "rb") as f:
                return pickle.load(f)
        except Exception:
            elog("model_load_pickle.log", f"pickle.load failed: {model_p}", with_exc=True)
            return None

def infer_intent(clf, texts):
    if clf is None:
        return ["其他"]*len(texts), [0.0]*len(texts), "no_model"
    try:
        if hasattr(clf, "predict_proba"):
            probs = clf.predict_proba(texts)
            labels = list(getattr(clf, "classes_", []))
            import numpy as np
            top_idx = probs.argmax(1)
            preds = [labels[i] for i in top_idx]
            confs = [float(probs[i, idx]) for i, idx in enumerate(top_idx)]
            return preds, confs, "model_ok"
        preds = clf.predict(texts)
        return list(preds), [1.0]*len(texts), "model_ok"
    except Exception:
        elog("model_predict.log", "predict failed; fallback to rules-only", with_exc=True)
        return ["其他"]*len(texts), [0.0]*len(texts), "predict_failed"

def load_rules():
    try:
        from smart_mail_agent.routing.intent_rules import load_rules as _lr
        return _lr()
    except Exception:
        PRIORITY = ["投訴","報價","技術支援","規則詢問","資料異動","其他"]
        RX = {
            "投訴": re.compile(r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)", re.I),
            "報價": re.compile(r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)", re.I),
            "技術支援": re.compile(r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)", re.I),
            "規則詢問": re.compile(r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)", re.I),
            "資料異動": re.compile(r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)", re.I),
            "其他": re.compile(r".*", re.I),
        }
        return PRIORITY, RX

def apply_threshold_and_rules(lbl, conf, text, thresholds, priority, rx_map):
    thr = thresholds.get(lbl, thresholds.get("其他", 0.40))
    routed = lbl if conf >= thr else "其他"
    if routed == "其他":
        hits = [k for k, rx in rx_map.items() if rx.search(text or "")]
        for k in priority:
            if k in hits:
                return k, f"rule:{k}"
    return routed, None

def choose_run(run_dir_arg: str):
    if run_dir_arg:
        p = Path(run_dir_arg)
        return p if p.is_absolute() else (ROOT / p)
    for d in list_e2e_dirs():
        if (d / "cases.jsonl").exists():
            return d
    return None

def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run-dir", default="")
    args = ap.parse_args(argv)

    if args.list:
        for p in list_e2e_dirs():
            print(p.as_posix(), "|", "cases.jsonl" if (p/"cases.jsonl").exists() else "-")
        return 0

    run = choose_run(args.run_dir)
    if not run or not run.exists():
        elog("run_pick.log", "no e2e run with cases.jsonl found")
        print("[FATAL] no e2e run with cases.jsonl found")
        return 2

    raw = (run/"cases.jsonl").read_text("utf-8", errors="ignore").splitlines()
    lines = [ln for ln in raw if ln.strip()]
    if not lines:
        elog("cases_empty.log", f"cases.jsonl is empty: {run.as_posix()}")
        print(f"[FATAL] cases.jsonl is empty: {run.as_posix()}")
        return 2

    thresholds = load_thresholds()
    PRIORITY, RX = load_rules()

    cases = [json.loads(x) for x in lines]
    texts = [safe_text(r) for r in cases]

    clf = load_intent_model()
    preds, confs, mode = infer_intent(clf, texts)

    out_nd  = run / "intent_reroute_suggestion.ndjson"
    out_csv = run / "intent_reroute_audit.csv"
    out_md  = run / "intent_reroute_summary.md"

    orig=[]; final=[]
    with open(out_nd, "w", encoding="utf-8") as fnd, open(out_csv, "w", encoding="utf-8") as fcsv:
        fcsv.write("case_id,orig_intent,orig_conf,final_intent,reason,mode\n")
        for r, lbl, conf, txt in zip(cases, preds, confs, texts):
            new_lbl, reason = apply_threshold_and_rules(lbl, conf, txt, thresholds, PRIORITY, RX)
            rec = {
                "case_id": r.get("case_id") or r.get("id"),
                "orig_intent": lbl, "orig_conf": conf,
                "final_intent": new_lbl, "reason": reason, "mode": mode
            }
            fnd.write(json.dumps(rec, ensure_ascii=False)+"\n")
            fcsv.write(f"{rec['case_id']},{lbl},{conf:.3f},{new_lbl},{reason or ''},{mode}\n")
            orig.append(lbl); final.append(new_lbl)

    c1, c2 = Counter(orig), Counter(final)
    keys = sorted(set(c1)|set(c2))
    lines_out = [f"- {k}: orig={c1.get(k,0)} -> final={c2.get(k,0)}" for k in keys]
    out_md.write_text(
        "# Intent reroute summary\n"
        f"- run_dir: {run.as_posix()}\n"
        f"- thresholds: {json.dumps(thresholds, ensure_ascii=False)}\n"
        f"- mode: {mode}\n\n"
        "## counts (orig -> final)\n" + "\n".join(lines_out) + "\n",
        encoding="utf-8"
    )
    print("[OK] write", out_nd.as_posix())
    print("[OK] write", out_csv.as_posix())
    print("[OK] write", out_md.as_posix())
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        pass
    except Exception:
        elog("fatal.log", "reroute fatal", with_exc=True)
        print("[FATAL] reroute failed")
