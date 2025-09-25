#!/usr/bin/env bash
set -Eeuo pipefail

TS="$(date +%F_%H%M%S)"
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
PRJ_LOG="${PROJ}/.sma_tools/logs/eval_external_${TS}.log"
TMP_LOG="${TMPDIR:-/tmp}/sma_eval_${TS}.log"

mkdir -p "$(dirname "$PRJ_LOG")"
# 同步寫 /tmp 與專案 log（不中斷也有 log）
exec > >(tee -a "$TMP_LOG" | tee -a "$PRJ_LOG") 2>&1
set -x
trap 'echo "[TRAP][ERR] line=$LINENO status=$? cmd=${BASH_COMMAND}"' ERR
trap 'echo "[TRAP][EXIT] status=$?"' EXIT

IN_RAW="${1:-}"
[ -n "$IN_RAW" ] || { echo "usage: $0 <external_test.jsonl>"; exit 2; }

normalize_path() {
python - "$IN_RAW" <<'PY'
import re, sys
p = sys.argv[1]
if p.startswith(('/', './')):
    print(p); raise SystemExit
m = re.match(r'^\\\\wsl\.localhost\\[^\\]+\\(.*)$', p)
if m:
    print('/' + m.group(1).replace('\\','/')); raise SystemExit
m = re.match(r'^([A-Za-z]):\\(.*)$', p)
if m:
    drive = m.group(1).lower()
    rest  = m.group(2).replace('\\','/')
    print('/mnt/' + drive + '/' + rest); raise SystemExit
print(p)
PY
}
IN="$(normalize_path)"
[ -f "$IN" ] || { echo "[ERR] file not found: $IN_RAW -> $IN"; exit 3; }

[ -d "$PROJ" ] || { echo "[ERR] project not found: $PROJ"; exit 4; }
cd "$PROJ"
mkdir -p .sma_tools/logs reports_auto data/intent

# venv
ACT_OK=0
if [ -f .venv/bin/activate ]; then . .venv/bin/activate && ACT_OK=1; fi
if [ $ACT_OK -eq 0 ] && [ -f "$HOME/.venv/sma/bin/activate" ]; then . "$HOME/.venv/sma/bin/activate" && ACT_OK=1; fi
[ $ACT_OK -eq 1 ] || { echo "[ERR] virtualenv not found"; exit 5; }

# env check
python -X faulthandler - <<'PY'
import importlib, numpy, scipy, sklearn
need=['numpy','scipy','sklearn']
miss=[m for m in need if importlib.util.find_spec(m) is None]
assert not miss, "missing:{}".format(miss)
print("[ENV] numpy={} scipy={} sklearn={}".format(numpy.__version__, scipy.__version__, sklearn.__version__))
PY

# compile whitelist
python -X faulthandler - <<'PY'
import py_compile
wh=[
  ".sma_tools/auto_augment_train.py",
  ".sma_tools/calibrate_and_card.py",
  ".sma_tools/route_predict.py",
  ".sma_tools/predict_full.py",
  ".sma_tools/extract_fields.py",
  ".sma_tools/priority_rules.py",
  ".sma_tools/eval_only.py",
]
for f in wh: py_compile.compile(f, doraise=True)
print("[OK] tools compile (whitelist)")
PY

# clean external
CLEAN=$(
python -X faulthandler - "$IN" <<'PY'
import json, re, sys, os
from collections import Counter
src = sys.argv[1]
PH = {"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

raw=[json.loads(ln) for ln in open(src,encoding="utf-8") if ln.strip()]

def k(r): return (r.get("label"), (r.get("meta") or {}).get("language"), r.get("text","").strip().lower())
seen=set(); clean=[]
for r in raw:
    if k(r) in seen: continue
    seen.add(k(r))
    bad=set(re.findall(r"<([A-Z_]+)>", r["text"])) - PH
    if bad: continue
    clean.append(r)

leaks=0; train=set()
snap="data/intent/train_used_export.jsonl"
if os.path.exists(snap):
    for ln in open(snap,encoding="utf-8"):
        if ln.strip():
            rr=json.loads(ln); train.add(k(rr))

filtered=[]
for r in clean:
    if k(r) in train:
        leaks+=1; continue
    filtered.append(r)

labs=[r["label"] for r in filtered]
langs=[(r.get("meta") or {}).get("language","unk") for r in filtered]
rep = []
rep.append("[CHECK] total_in = {}".format(len(raw)))
rep.append("[CHECK] dup_internal_removed = {}".format(len(raw)-len(clean)))
rep.append("[CHECK] leak_vs_training_removed = {}".format(leaks))
rep.append("[CHECK] total_clean = {}".format(len(filtered)))
rep.append("[CHECK] labels = {}".format(dict(Counter(labs))))
rep.append("[CHECK] languages = {}".format(dict(Counter(langs))))
os.makedirs("reports_auto", exist_ok=True)
open("reports_auto/external_check.txt","w",encoding="utf-8").write("\n".join(rep)+"\n")

outp="data/intent/external_realistic_test.clean.jsonl"
with open(outp,"w",encoding="utf-8") as w:
    for r in filtered: w.write(json.dumps(r,ensure_ascii=False)+"\n")
print(outp)
PY
)
[ -f "$CLEAN" ] || { echo "[ERR] clean file not produced"; exit 6; }
echo "[11:43:23] clean = $CLEAN"

# model
MODEL="artifacts/intent_svm_plus_auto_cal.pkl"
[ -f "$MODEL" ] || MODEL="artifacts/intent_svm_plus_auto.pkl"
echo "[11:43:23] model = $MODEL"

# eval (無 f-string)
python -X faulthandler - "$MODEL" "$CLEAN" <<'PY'
import json, sys, pickle, re, os
from pathlib import Path
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import classification_report, confusion_matrix

model = sys.argv[1]; test = sys.argv[2]
bundle=pickle.load(open(model,"rb"))
rows=[json.loads(x) for x in open(test,encoding="utf-8") if x.strip()]
texts=[r["text"] for r in rows]

def rx(texts,srcs):
    regs=[re.compile(p,re.I) for p in srcs]
    mat=[[1 if rg.search(t) else 0 for rg in regs] for t in texts]
    return csr_matrix(np.array(mat,dtype=np.float32))

X=hstack([bundle["char_vec"].transform(texts),
          bundle["word_vec"].transform(texts),
          rx(texts,bundle["regex_sources"])])

clf=bundle["clf"]; labels=clf.classes_.tolist()
pred=clf.predict(X)

report = classification_report([r["label"] for r in rows], pred, labels=labels, digits=3, zero_division=0)
cm = confusion_matrix([r["label"] for r in rows], pred, labels=labels)

Path("reports_auto").mkdir(parents=True, exist_ok=True)
open("reports_auto/external_eval_manual.txt","w",encoding="utf-8").write(
    report+"\n[CONFUSION]\n\t"+"\t".join(labels)+"\n" + "\n".join(
        lab+"\t"+"\t".join(map(str,row)) for lab,row in zip(labels,cm)
    )+"\n"
)

with open("reports_auto/external_preds.jsonl","w",encoding="utf-8") as w:
    for r,yhat in zip(rows,pred):
        w.write(json.dumps(
            {"id":r.get("id"),"text":r["text"],"label":r["label"],"pred":yhat,
             "lang":(r.get("meta") or {}).get("language")},
            ensure_ascii=False
        )+"\n")

with open("reports_auto/external_errors.tsv","w",encoding="utf-8") as w:
    w.write("id\tlang\tgold\tpred\ttext\n")
    for r,yhat in zip(rows,pred):
        if r["label"]!=yhat:
            txt  = r["text"].replace("\t"," ").replace("\n"," ")
            lang = (r.get("meta") or {}).get("language","")
            w.write("{}\t{}\t{}\t{}\t{}\n".format(
                r.get("id",""), lang, r["label"], yhat, txt
            ))
print("[DONE]")
print(" -", test)
print(" - reports_auto/external_check.txt")
print(" - reports_auto/external_eval_manual.txt")
print(" - reports_auto/external_preds.jsonl")
print(" - reports_auto/external_errors.tsv")
PY

echo "[LOG] /tmp: ${TMP_LOG}"
echo "[LOG] proj: ${PRJ_LOG}"
