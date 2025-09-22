#!/usr/bin/env bash
set -Eeuo pipefail

MODEL_PATH="${MODEL:-$1}"; shift || true
TEST_PATH="${1:-data/intent/external_realistic_test.clean.jsonl}"; shift || true
OUT_PREFIX="${1:-reports_auto/ext_eval}"; shift || true

python - <<'PY'
import os, sys, json, pickle, traceback
from pathlib import Path
from collections import Counter
import numpy as np

# -------- stubs: 防止舊 pkl 的自訂類找不到 --------
try:
    from scipy import sparse
except Exception:
    print("[FATAL] SciPy 未安裝，請啟用 venv", file=sys.stderr); sys.exit(2)

class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw): self.n_features=int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), self.n_features), dtype="float64")
class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X): return sparse.csr_matrix((len(X), 0), dtype="float64")
# -------------------------------------------------

root = Path.cwd()
# 參數
env_model = os.environ.get("MODEL")
cli_model = sys.argv[1] if len(sys.argv)>1 else None
cli_test  = sys.argv[2] if len(sys.argv)>2 else "data/intent/external_realistic_test.clean.jsonl"
cli_out   = sys.argv[3] if len(sys.argv)>3 else "reports_auto/ext_eval"

# 模型路徑決策：優先 env，再 CLI
candidates = []
if env_model: candidates.append(Path(env_model))
if cli_model: candidates.append(Path(cli_model))
candidates += [
    root/"artifacts/intent_pro_cal.pkl",            # 可能壞的
    root/"artifacts/intent_svm_plus_auto_cal.pkl",  # baseline
]
model_path = None
for p in candidates:
    if p and p.exists():
        # 嘗試載入，壞就跳過
        try:
            obj = pickle.load(open(p,"rb"))
            model_path = p
            model_obj  = obj
            print(f"[MODEL] using {p}")
            break
        except Exception as e:
            print(f"[SKIP] {p.name}: {e.__class__.__name__}: {e}")

if model_path is None:
    print("[FATAL] 沒有任何可用模型（含 Pro/Auto_cal）", file=sys.stderr); sys.exit(3)

# 若是字典，盡力抽出 pipeline
pipe = None
obj = model_obj
def is_pipe(o): return hasattr(o, "predict") and (hasattr(o,"transform") or hasattr(o,"named_steps") or hasattr(o,"steps"))
if is_pipe(obj):
    pipe = obj
elif isinstance(obj, dict):
    for k in ("pipeline","sk_pipeline","pipe"):
        v = obj.get(k)
        if v is not None and is_pipe(v):
            pipe = v; break
    if pipe is None and {"word_vec","char_vec","clf"} <= set(obj.keys()):
        # 組合 word/char +（可選）pad → clf
        from sklearn.pipeline import Pipeline, FeatureUnion
        parts=[]
        for name in ("word_vec","char_vec","pad"):
            if name in obj and obj[name] is not None: parts.append((name, obj[name]))
        feats = FeatureUnion(parts)
        pipe = Pipeline([("features", feats), ("clf", obj["clf"])])
if pipe is None:
    print(f"[FATAL] {model_path.name} 不是可推論的 Pipeline，也無法從 dict 組回", file=sys.stderr)
    sys.exit(4)

# 讀測試集
test_path = Path(cli_test)
rows=[]
with open(test_path,"r",encoding="utf-8") as f:
    for ln in f:
        o=json.loads(ln)
        y=o.get("label") or o.get("intent") or o.get("y")
        t=o.get("text") or (o.get("subject","")+"\n"+o.get("body",""))
        rows.append((o.get("id") or o.get("doc_id") or "", o.get("lang") or "", y, (t or "").strip()))
X=[t for _,_,_,t in rows]; Y=[y for _,_,y,_ in rows]; IDS=[i for i,_,_,_ in rows]; LANG=[l for _,l,_,_ in rows]

# 推論
y_pred = pipe.predict(X)
labels = sorted(list({y for y in Y if y is not None}))

# 指標
def cmatrix(y_true, y_pred, labels):
    idx = {lab:i for i,lab in enumerate(labels)}
    M = np.zeros((len(labels),len(labels)), dtype=int)
    for a,b in zip(y_true,y_pred):
        if a in idx and b in idx: M[idx[a], idx[b]] += 1
    return M
def prf_counts(y_true, y_pred, labels):
    out={}
    for lab in labels:
        tp=fp=fn=0
        for yt,yp in zip(y_true,y_pred):
            tp += (yt==lab and yp==lab)
            fp += (yt!=lab and yp==lab)
            fn += (yt==lab and yp!=lab)
        P = tp/(tp+fp) if (tp+fp)>0 else 0.0
        R = tp/(tp+fn) if (tp+fn)>0 else 0.0
        F = (2*P*R/(P+R)) if (P+R)>0 else 0.0
        out[lab]={"tp":tp,"fp":fp,"fn":fn,"P":P,"R":R,"F1":F}
    acc = sum(yt==yp for yt,yp in zip(y_true,y_pred))/len(y_true)
    macro = float(np.mean([out[lab]["F1"] for lab in labels])) if labels else 0.0
    return acc, macro, out

acc, macro, by = prf_counts(Y, y_pred, labels)
M = cmatrix(Y, y_pred, labels)

# 輸出
out_prefix = Path(cli_out)
out_prefix.parent.mkdir(parents=True, exist_ok=True)
p_eval = Path(str(out_prefix) + "_eval.txt")
p_conf = Path(str(out_prefix) + "_confusion.tsv")
p_errs = Path(str(out_prefix) + "_errors.tsv")

with open(p_eval,"w",encoding="utf-8") as fo:
    fo.write(f"pairs={len(Y)}\n")
    fo.write(f"Accuracy={acc:.4f}\n")
    fo.write(f"MacroF1={macro:.4f}\n")
    for lab in labels:
        d=by[lab]
        fo.write(f"{lab}: P={d['P']:.4f} R={d['R']:.4f} F1={d['F1']:.4f} (tp={d['tp']},fp={d['fp']},fn={d['fn']})\n")

with open(p_conf,"w",encoding="utf-8") as fo:
    fo.write("label\t" + "\t".join(labels) + "\n")
    for i,lab in enumerate(labels):
        fo.write(lab + "\t" + "\t".join(str(int(x)) for x in M[i]) + "\n")

with open(p_errs,"w",encoding="utf-8") as fo:
    fo.write("id\tlang\tgold\tpred\ttext\n")
    for i,(idx,lang,yt,txt) in enumerate(rows):
        yp = y_pred[i]
        if yp != yt:
            san = (txt or "").replace("\t"," ").replace("\n"," ")
            fo.write(f"{idx}\t{lang}\t{yt}\t{yp}\t{san[:500]}\n")

print("[OUT]", p_eval, p_conf, p_errs)
PY
