#!/usr/bin/env python3
# 安全版：不使用 f-strings，避免「f-string expression part cannot include a backslash」問題
import argparse, json, sys
from pathlib import Path

# --- 相依載入（兼容別名） ---
try:
    from _spam_common import signals, text_of
except Exception:
    # 後備：直接從 scripts/_sma_common 匯入
    sys.path.insert(0, "scripts")
    from _sma_common import spam_signals as signals, text_of  # type: ignore

import joblib
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from sklearn.pipeline import Pipeline

def read_jsonl(p):
    for ln in Path(p).read_text(encoding="utf-8", errors="ignore").splitlines():
        if ln.strip():
            yield json.loads(ln)

def load_model(p):
    obj = joblib.load(p)
    # 相容 dict 存檔（vect + cal）
    if isinstance(obj, dict) and ("vect" in obj and "cal" in obj):
        return Pipeline([("vect", obj["vect"]), ("cal", obj["cal"])])
    return obj

def evaluate(y_true, y_hat):
    P, R, F, _ = precision_recall_fscore_support(y_true, y_hat, average=None, labels=[0,1])
    cm = confusion_matrix(y_true, y_hat, labels=[0,1]).tolist()
    macro = (F[0] + F[1]) / 2.0
    return {
        "macroF1": float(macro),
        "ham": {"P": float(P[0]), "R": float(R[0]), "F1": float(F[0])},
        "spam": {"P": float(P[1]), "R": float(R[1]), "F1": float(F[1])},
        "cm": cm,
    }

def write_eval_txt(path, tag, m):
    lines = []
    lines.append("[{}] Macro-F1={:.4f}".format(tag, m["macroF1"]))
    lines.append("Ham  P/R/F1 = {P:.3f}/{R:.3f}/{F1:.3f}".format(**m["ham"]))
    lines.append("Spam P/R/F1 = {P:.3f}/{R:.3f}/{F1:.3f}".format(**m["spam"]))
    lines.append("Confusion = {}".format(m["cm"]))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--out", default="reports_auto/prod_quick_report.md")
    args = ap.parse_args()

    data = list(read_jsonl(args.data))
    if not data:
        print("[FATAL] input data is empty: {}".format(args.data))
        sys.exit(2)

    th = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    thr = float(th.get("threshold", 0.5))
    smin = int(th.get("signals_min", 3))

    pipe = load_model(args.model)

    X = [text_of(r) for r in data]
    y = np.array([1 if r.get("label") == "spam" else 0 for r in data], dtype=int)

    # TEXT
    prob = pipe.predict_proba(X)[:, 1]
    y_text = (prob >= thr).astype(int)

    # RULE
    sig = np.array([signals(r) for r in data], dtype=int)
    y_rule = (sig >= smin).astype(int)

    # ENSEMBLE (OR)
    y_ens = np.maximum(y_text, y_rule)

    # Metrics
    m_text = evaluate(y, y_text)
    m_rule = evaluate(y, y_rule)
    m_ens  = evaluate(y, y_ens)

    # Output files (與原約定相容)
    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    write_eval_txt(out_dir / "prod_eval_text_only.txt", "TEXT", m_text)
    write_eval_txt(out_dir / "prod_eval_rule_only.txt", "RULE", m_rule)
    write_eval_txt(out_dir / "prod_eval_ensemble.txt",  "ENSEMBLE", m_ens)

    # 錯誤清單（TSV；避免 f-string）
    fn_path = out_dir / "prod_errors_fn.tsv"
    fp_path = out_dir / "prod_errors_fp.tsv"
    with fn_path.open("w", encoding="utf-8") as wfn, fp_path.open("w", encoding="utf-8") as wfp:
        wfn.write("id\tsubject\n")
        wfp.write("id\tsubject\n")
        for r, yt, ye in zip(data, y.tolist(), y_ens.tolist()):
            subj = (r.get("subject") or "").replace("\t", " ")[:200]
            if yt == 1 and ye == 0:
                wfn.write("{}\t{}\n".format(r.get("id", ""), subj))
            if yt == 0 and ye == 1:
                wfp.write("{}\t{}\n".format(r.get("id", ""), subj))

    # Quick report（Markdown）
    md = []
    md.append("# Spam quick report")
    md.append("")
    md.append("- TEXT Macro-F1: {:.4f}".format(m_text["macroF1"]))
    md.append("- RULE Macro-F1: {:.4f}".format(m_rule["macroF1"]))
    md.append("- ENSEMBLE Macro-F1: {:.4f}".format(m_ens["macroF1"]))
    Path(args.out).write_text("\n".join(md) + "\n", encoding="utf-8")

    print("[TEXT]  Macro-F1={:.4f}".format(m_text["macroF1"]))
    print("[RULE]  Macro-F1={:.4f}".format(m_rule["macroF1"]))
    print("[ENS]   Macro-F1={:.4f}".format(m_ens["macroF1"]))
    print("[OK] wrote {}".format(args.out))

if __name__ == "__main__":
    main()
