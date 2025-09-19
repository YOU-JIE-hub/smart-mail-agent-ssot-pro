#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, re, sys
from typing import List, Tuple
import numpy as np

# sklearn / joblib
try:
    import joblib
    from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score
except Exception as e:
    print(f"[FATAL] need scikit-learn / joblib: {e}", file=sys.stderr)
    sys.exit(2)

RE_URL = re.compile(r"https?://[^\s)>\]]+", re.I)
SUS_TLD = {".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT = {".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW      = ["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
           "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]

def load_jsonl(fp: pathlib.Path):
    with fp.open("r", encoding="utf-8", errors="ignore") as r:
        for ln in r:
            ln = ln.strip()
            if not ln: continue
            yield json.loads(ln)

def to_text(rec):
    return (rec.get("subject","") + " \n " + rec.get("body",""))

def signals(rec) -> int:
    t = (rec.get("subject","") + " " + rec.get("body","")).lower()
    urls = RE_URL.findall(t)
    atts = [(a or "").lower() for a in rec.get("attachments",[]) if a]
    s = 0
    if urls: s += 1
    if any(u.lower().endswith(tld) for u in urls for tld in SUS_TLD): s += 1
    if any(k in t for k in KW): s += 1
    if any(a.endswith(ext) for a in atts for ext in SUS_EXT): s += 1
    if ("account" in t) and (("verify" in t) or ("reset" in t) or ("login" in t) or ("signin" in t)): s += 1
    if ("帳戶" in t) and (("驗證" in t) or ("重設" in t) or ("登入" in t)): s += 1
    return s

def load_text_model():
    mp1 = pathlib.Path("artifacts_prod/model_pipeline.pkl")
    mp2 = pathlib.Path("artifacts_prod/text_lr_platt.pkl")
    if mp1.exists():
        mdl = joblib.load(mp1)
        return mdl, "pipeline", str(mp1)
    if mp2.exists():
        mdl = joblib.load(mp2)  # {'vect':..., 'cal': CalibratedClassifierCV}
        return mdl, "dict", str(mp2)
    raise SystemExit("[FATAL] missing artifacts_prod/model_pipeline.pkl (or text_lr_platt.pkl)")

def predict_proba(model, mode: str, texts: List[str]) -> np.ndarray:
    if mode == "pipeline":
        # sklearn Pipeline with predict_proba
        return model.predict_proba(texts)[:,1]
    # dict: {'vect': TfidfVectorizer, 'cal': CalibratedClassifierCV}
    vect = model.get("vect"); cal = model.get("cal")
    Xt = vect.transform(texts)
    return cal.predict_proba(Xt)[:,1]

def dump_errors(fn_path: pathlib.Path, fp_path: pathlib.Path, ids: List[str], recs: List[dict], y: np.ndarray, yhat: np.ndarray):
    fn_rows = []
    fp_rows = []
    for _id, r, yt, yh in zip(ids, recs, y, yhat):
        if yt==1 and yh==0:   # FN
            subj = (r.get("subject") or "")[:200].replace("\t"," ")
            fn_rows.append((_id, subj))
        elif yt==0 and yh==1: # FP
            subj = (r.get("subject") or "")[:200].replace("\t"," ")
            fp_rows.append((_id, subj))
    with fn_path.open("w", encoding="utf-8") as w:
        for i, subj in fn_rows:
            w.write(f"{i}\t{subj}\n")
    with fp_path.open("w", encoding="utf-8") as w:
        for i, subj in fp_rows:
            w.write(f"{i}\t{subj}\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="JSONL with {id,subject,body,attachments,label}")
    ap.add_argument("--out",  default="reports_auto/spam_eval.txt")
    args = ap.parse_args()

    data_path = pathlib.Path(args.data)
    out_path  = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # thresholds
    thr_path = pathlib.Path("artifacts_prod/ens_thresholds.json")
    if not thr_path.exists():
        raise SystemExit("[FATAL] missing artifacts_prod/ens_thresholds.json")
    thr = json.loads(thr_path.read_text(encoding="utf-8"))
    threshold = float(thr.get("threshold", 0.44))
    smin      = int(thr.get("signals_min", 3))

    # model
    model, mode, model_src = load_text_model()

    # data
    recs = list(load_jsonl(data_path))
    ids  = [r.get("id", f"rec-{i:05d}") for i,r in enumerate(recs)]
    Xtxt = [to_text(r) for r in recs]
    y    = np.array([1 if (r.get("label")=="spam") else 0 for r in recs], dtype=int)

    # predictions
    p_text = predict_proba(model, mode, Xtxt)
    y_text = (p_text >= threshold).astype(int)

    s_rule = np.array([signals(r) for r in recs], dtype=int)
    y_rule = (s_rule >= smin).astype(int)

    y_ens  = np.maximum(y_text, y_rule)

    def metrics(y_true, y_pred):
        P,R,F,_ = precision_recall_fscore_support(y_true, y_pred, average=None, labels=[0,1])
        cm = confusion_matrix(y_true, y_pred, labels=[0,1]).tolist()
        macro = float((F[0]+F[1])/2)
        return macro, P, R, F, cm

    m_text = metrics(y, y_text)
    m_rule = metrics(y, y_rule)
    m_ens  = metrics(y, y_ens)

    # AUCs for text only
    roc = float(roc_auc_score(y, p_text)) if len(set(y))==2 else float("nan")
    prc = float(average_precision_score(y, p_text)) if len(set(y))==2 else float("nan")

    # write errors (ensemble)
    dump_errors(pathlib.Path("reports_auto/prod_errors_fn.tsv"),
                pathlib.Path("reports_auto/prod_errors_fp.tsv"),
                ids, recs, y, y_ens)

    with out_path.open("w", encoding="utf-8") as w:
        w.write(f"DATA={data_path}  N={len(y)}\n")
        w.write(f"MODEL={model_src}  THRESHOLD={threshold}  SIGNALS_MIN={smin}\n\n")

        def fmt(tag, M):
            macro, P, R, F, cm = M
            return (f"[{tag}] Macro-F1={macro:.4f} | "
                    f"Ham {P[0]:.3f}/{R[0]:.3f}/{F[0]:.3f} | "
                    f"Spam {P[1]:.3f}/{R[1]:.3f}/{F[1]:.3f} | "
                    f"CM={cm}\n")
        w.write(fmt("TEXT", m_text))
        w.write(fmt("RULE", m_rule))
        w.write(fmt("ENSEMBLE", m_ens))
        w.write(f"\nTEXT ROC-AUC={roc:.3f}  PR-AUC={prc:.3f}\n")

    print(f"[OK] wrote {out_path}")
