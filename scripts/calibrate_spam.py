import os, json, math, gzip, io, sys, re, hashlib
from pathlib import Path
import numpy as np

# 盡量不依賴額外套件；有就用，沒有就降級
try:
    import pandas as pd
except Exception:
    pd = None
try:
    from sklearn.metrics import accuracy_score, roc_auc_score, average_precision_score, f1_score
    import joblib
except Exception as e:
    print("[FATAL] need scikit-learn & joblib in venv:", e, file=sys.stderr); sys.exit(2)

SPAM_PKL = os.getenv("SPAM_PKL", "/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl")

DATA_CANDIDATES = [
    "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent/data/benchmarks/spamassassin.jsonl",
    "/home/youjie/projects/smart-mail-agent/spamassassin.jsonl",
    # reports_auto/export 副本
    "/home/youjie/projects/smart-mail-agent-ssot-pro/reports_auto/export/20250916T012142/stage/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/reports_auto/export/20250916T014311/bundle/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/reports_auto/export/20250916T005124/stage/data/spam_eval/dataset.jsonl",
    "/home/youjie/projects/smart-mail-agent-ssot-pro/reports_auto/export/20250916T050438/stage/data/spam_eval/dataset.jsonl",
]

OUT = Path(sys.argv[sys.argv.index("--out")+1]) if "--out" in sys.argv else Path("reports_auto/pro/latest")
OUT.mkdir(parents=True, exist_ok=True)

def read_jsonl(p: Path):
    openers = [open]
    if p.suffix == ".gz":
        openers = [gzip.open]
    for op in openers:
        try:
            with op(p, "rt", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line=line.strip()
                    if not line: continue
                    try:
                        yield json.loads(line)
                    except Exception:
                        pass
            return
        except Exception:
            continue

def pick_text(obj):
    for k in ("text","body","content","raw","mail","message"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    # 組合欄位
    parts=[]
    for k in ("subject","from","to"):
        v=obj.get(k); 
        if isinstance(v,str) and v.strip(): parts.append(f"{k}: {v}")
    return "\n".join(parts) if parts else ""

def pick_label(obj):
    v = obj.get("label", obj.get("y", obj.get("target")))
    if v is None: return None
    s = str(v).strip().lower()
    if s in {"1","spam","true","yes"}: return 1
    if s in {"0","ham","false","no"}: return 0
    try:
        n = int(float(s))
        return 1 if n==1 else 0
    except Exception:
        return None

def load_dataset():
    for p in DATA_CANDIDATES:
        pp = Path(p)
        if pp.exists():
            X, y = [], []
            for obj in read_jsonl(pp):
                t = pick_text(obj); lab = pick_label(obj)
                if t is None or t=="" or lab is None: continue
                X.append(t); y.append(lab)
            if X:
                print(f"[OK] dataset: {pp} n={len(X)} pos={sum(y)} neg={len(y)-sum(y)}")
                return X, np.array(y), pp
    print("[FATAL] no dataset found", file=sys.stderr)
    sys.exit(3)

def sigmoid(x):
    x = np.clip(x, -30, 30)
    return 1.0/(1.0+np.exp(-x))

def predict_proba1(model, X):
    if hasattr(model, "predict_proba"):
        P = model.predict_proba(X)
        if P.shape[1]==2: return P[:,1]
        if P.shape[1]==1: return P[:,0]
    if hasattr(model, "decision_function"):
        s = model.decision_function(X)
        if s.ndim==1: return sigmoid(s)
        if s.ndim==2 and s.shape[1]==2: return sigmoid(s[:,1]-s[:,0])
    # fallback: predict -> {0,1}
    yhat = model.predict(X)
    return yhat.astype(float)

def ece_score(y_true, p, n_bins=20):
    bins = np.linspace(0.0, 1.0, n_bins+1)
    idx = np.digitize(p, bins) - 1
    ece = 0.0
    rows = []
    for b in range(n_bins):
        m = idx==b
        if not np.any(m): 
            rows.append((bins[b], bins[b+1], 0, 0.0, 0.0))
            continue
        conf = p[m].mean()
        acc  = ( (p[m]>=0.5).astype(int) == y_true[m] ).mean()
        e    = abs(acc - conf)
        w    = m.mean()
        ece += e*w
        rows.append((bins[b], bins[b+1], m.sum(), float(acc), float(conf)))
    return float(ece), rows

def sweep_threshold(y, p):
    out=[]
    for t in np.linspace(0.01, 0.99, 99):
        yhat = (p>=t).astype(int)
        acc  = (yhat==y).mean()
        f1   = f1_score(y, yhat, zero_division=0)
        out.append((t, float(acc), float(f1)))
    out.sort(key=lambda x: (-x[2], -x[1]))  # 先 F1 再 Acc
    return out

def write_tsv(path, rows, header):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

def main():
    X, y, ds_path = load_dataset()
    model = joblib.load(SPAM_PKL)
    p = predict_proba1(model, X)

    acc = ( (p>=0.5).astype(int) == y ).mean()
    roc = None
    pr  = None
    try:
        if len(set(y))==2:
            roc = roc_auc_score(y, p)
            pr  = average_precision_score(y, p)
    except Exception:
        pass

    ece, rel_rows = ece_score(y, p, n_bins=20)
    sweep = sweep_threshold(y, p)
    best_t, best_acc, best_f1 = sweep[0]

    # 輸出
    OUT.mkdir(parents=True, exist_ok=True)
    write_tsv(OUT/"spam_reliability.tsv", rel_rows, ["bin_lo","bin_hi","count","bin_acc","bin_conf"])
    write_tsv(OUT/"spam_threshold_sweep.tsv", sweep, ["threshold","acc","f1"])

    meta = {
        "dataset": str(ds_path),
        "model": SPAM_PKL,
        "n": int(len(y)),
        "pos": int(y.sum()),
        "neg": int(len(y)-y.sum()),
        "metrics": {
            "accuracy_default_0.5": float(acc),
            "roc_auc": None if roc is None else float(roc),
            "pr_auc":  None if pr  is None else float(pr),
            "ece": float(ece),
        },
        "recommend_threshold": float(best_t),
        "recommend_at_t": {"acc": float(best_acc), "f1": float(best_f1)},
    }
    (OUT/"spam_calibration.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 追加到 summary.md（若存在）
    smd = OUT/"summary.md"
    block = [
        "\n## SPAM（校準增補）\n",
        f"- 資料集：`{ds_path}`\n",
        f"- ECE：{meta['metrics']['ece']:.3f}\n",
        f"- 建議閾值：{meta['recommend_threshold']:.2f}（F1={meta['recommend_at_t']['f1']:.3f} / Acc={meta['recommend_at_t']['acc']:.3f}）\n",
        f"- 產物：`spam_reliability.tsv`, `spam_threshold_sweep.tsv`, `spam_calibration.json`\n",
    ]
    try:
        with open(smd, "a", encoding="utf-8") as f: f.writelines(block)
    except Exception:
        (OUT/"spam_calibration.md").write_text("".join(block), encoding="utf-8")

    print(f"[OK] calib -> {OUT}")
if __name__=="__main__":
    main()
