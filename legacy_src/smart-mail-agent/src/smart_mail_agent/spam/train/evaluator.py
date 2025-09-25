#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/train/evaluator.py
# 模組用途：載入規則模型與（可選）LLM 分數，輸出指標達標與否
from __future__ import annotations
import json, os
from pathlib import Path
from typing import List
import numpy as np
from joblib import load
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, f1_score
from .features import load_rules, extract
from ..llm_scorer import score_likelihood

def _read_jsonl(p: Path) -> list[dict]:
    out = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def evaluate(jsonl_path: str, rules_path: str, model_path: str, thresholds_path: str,
             w_rule: float=1.0, w_llm: float=0.0, out_txt: str="reports_auto/spam_eval.txt") -> None:
    rules = load_rules(rules_path)
    data = _read_jsonl(Path(jsonl_path))
    bundle = load(model_path)
    clf = bundle["sk"]

    X = np.array([[extract(x, rules)[k] for k in ["keyword_hits","url_ratio","risky_tld_hits","attachment_risky_hits","money_symbols","non_ascii_ratio","sender_black","bias"]] for x in data], dtype=float)
    p_rule = clf.predict_proba(X)[:,1]
    p_llm = np.array([score_likelihood(x) for x in data], dtype=float) if w_llm>0 else np.zeros_like(p_rule)
    p = np.clip(w_rule*p_rule + w_llm*p_llm, 0.0, 1.0)

    thr = float(json.loads(Path(thresholds_path).read_text(encoding="utf-8"))["threshold"])
    y = np.array([1 if (x.get("label")=="spam") else 0 for x in data], dtype=int)
    yhat = (p >= thr).astype(int)

    pr, rc, f1, _ = precision_recall_fscore_support(y, yhat, average=None, labels=[0,1], zero_division=0)
    macro = f1_score(y, yhat, average="macro")
    cm = confusion_matrix(y, yhat, labels=[0,1]).tolist()

    lines = []
    lines.append(f"[SPAM][EVAL] macro_f1={macro:.4f} thr={thr:.2f} w_rule={w_rule:.2f} w_llm={w_llm:.2f}")
    lines.append(f"[SPAM][EVAL] ham  P/R/F1 = {pr[0]:.3f}/{rc[0]:.3f}/{f1[0]:.3f}")
    lines.append(f"[SPAM][EVAL] spam P/R/F1 = {pr[1]:.3f}/{rc[1]:.3f}/{f1[1]:.3f}")
    lines.append(f"[SPAM][EVAL] confusion = {cm}")

    Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(out_txt).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def _dump_errors(path, data, y, yhat, p, feats_order, rules):
    out=Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with out.open("w", encoding="utf-8", newline="") as f:
        w=csv.writer(f, delimiter="\t")
        w.writerow(["id","label","pred","prob","subject","from","keyword_hits","url_ratio","risky_tld_hits","attachment_risky_hits","money_symbols","non_ascii_ratio","sender_black"])
        for i,(ex,yt,yp,pp) in enumerate(zip(data,y,yhat,p)):
            if yt!=yp:
                feats = __import__("smart_mail_agent.spam.train.features", fromlist=["extract"]).extract(ex, rules)
                w.writerow([
                    ex.get("id",str(i)), "spam" if yt==1 else "ham", "spam" if yp==1 else "ham", f"{pp:.4f}",
                    (ex.get("subject") or "").replace("\t"," ").replace("\n"," "), ex.get("from",""),
                    feats.get("keyword_hits",0), feats.get("url_ratio",0), feats.get("risky_tld_hits",0),
                    feats.get("attachment_risky_hits",0), feats.get("money_symbols",0), feats.get("non_ascii_ratio",0), feats.get("sender_black",0)
                ])
    return str(out)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
    ap.add_argument("--model", default="artifacts/spam_rules_lr.pkl")
    ap.add_argument("--thresholds", default="artifacts/spam_thresholds.json")
    ap.add_argument("--w-rule", type=float, default=1.0)
    ap.add_argument("--w-llm", type=float, default=0.0)
    ap.add_argument("--out", default="reports_auto/spam_eval.txt")
    ap.add_argument("--errors-tsv", default=None)
    args = ap.parse_args()
    # 執行評測
    evaluate(args.data, args.rules, args.model, args.thresholds, args.w_rule, args.w_llm, args.out)
    # 錯誤樣本輸出（可選）
    if args.errors_tsv:
        import json, numpy as np
        from joblib import load
        rules = load_rules(args.rules)
        data = _read_jsonl(Path(args.data))
        bundle = load(args.model); clf=bundle["sk"]
        X = np.array([[extract(x, rules)[k] for k in ["keyword_hits","url_ratio","risky_tld_hits","attachment_risky_hits","money_symbols","non_ascii_ratio","sender_black","bias"]] for x in data], dtype=float)
        p_rule = clf.predict_proba(X)[:,1]
        from ..llm_scorer import score_likelihood
        import numpy as np
        p_llm = np.array([score_likelihood(x) for x in data], dtype=float) if args.w_llm>0 else np.zeros_like(p_rule)
        p = np.clip(args.w_rule*p_rule + args.w_llm*p_llm, 0.0, 1.0)
        thr = float(json.loads(Path(args.thresholds).read_text(encoding="utf-8"))["threshold"])
        y = np.array([1 if (x.get("label")=="spam") else 0 for x in data], dtype=int)
        yhat = (p >= thr).astype(int)
        path = _dump_errors(args.errors_tsv, data, y, yhat, p, None, rules)
        print(f"[SPAM][EVAL] errors_tsv={path}")

