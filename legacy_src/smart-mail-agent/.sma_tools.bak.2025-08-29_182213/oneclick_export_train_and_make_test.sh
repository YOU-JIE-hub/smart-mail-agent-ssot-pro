#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJ"
([ -f .venv/bin/activate ] && . .venv/bin/activate) || ([ -f "$HOME/.venv/sma/bin/activate" ] && . "$HOME/.venv/sma/bin/activate") || true

python - <<'PY'
import json, re, random, os, pickle
from pathlib import Path
from collections import Counter
random.seed(20250901)

ROOT=Path(".")
SPLTA=ROOT/"data/intent_split_auto"
SPLT =ROOT/"data/intent_split"
FULL =ROOT/"data/intent/i_20250901_full.jsonl"
HC   =ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB   =ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO =ROOT/"data/intent/i_20250901_auto_aug.jsonl"
OUT_DIR=ROOT/"reports_auto"; OUT_DIR.mkdir(parents=True, exist_ok=True)
TRAIN_EXPORT=ROOT/"data/intent/train_used_export.jsonl"
TEST_EXPORT =ROOT/"data/intent/external_test_auto.jsonl"
SUMMARY=OUT_DIR/"sets_summary.txt"

def R(p):
    if not p or not Path(p).exists(): return []
    out=[]
    for ln in Path(p).read_text(encoding="utf-8").splitlines():
        ln=ln.strip()
        if ln: out.append(json.loads(ln))
    return out

def W(rows,p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n", encoding="utf-8")

def norm_key(t:str)->str:
    t=t.lower()
    t=re.sub(r"\s+","",t)
    t=re.sub(r"[^\w\u4e00-\u9fff<>]+","",t)
    return t

# 1) 找出「實際用於訓練的資料」：優先採用 data/intent_split_auto/{train,val}.jsonl，其次 data/intent_split/{train,val}.jsonl
src="(reconstructed)"
train_rows=[]
if (SPLTA/"train.jsonl").exists() and (SPLTA/"val.jsonl").exists():
    train_rows = R(SPLTA/"train.jsonl") + R(SPLTA/"val.jsonl")
    src="data/intent_split_auto"
elif (SPLT/"train.jsonl").exists() and (SPLT/"val.jsonl").exists():
    train_rows = R(SPLT/"train.jsonl") + R(SPLT/"val.jsonl")
    src="data/intent_split"

# 如果都沒有，就把 FULL/HC/CB/AUTO 合併去重，做一次臨時 split（只為了能匯出 train_used）
if not train_rows:
    pool = R(FULL) + R(HC) + R(CB) + R(AUTO)
    seen=set(); clean=[]
    for r in pool:
        k=(r.get("label"), r.get("meta",{}).get("language"), norm_key(r.get("text","")))
        if k in seen: continue
        seen.add(k); clean.append(r)
    # 8:1:1 split，train_used = train+val
    labels=[r["label"] for r in clean]
    # 手寫簡單分層：先按label分桶後切
    by= {}
    for r in clean: by.setdefault(r["label"], []).append(r)
    train_rows=[]; val=[]; tst=[]
    for lab, arr in by.items():
        n=len(arr); t1=max(1, int(n*0.8)); t2=max(1, int(n*0.1))
        random.shuffle(arr)
        train_rows += arr[:t1]
        val        += arr[t1:t1+t2]
        tst        += arr[t1+t2:]
    src="FULL/HC/CB/AUTO dedup (temp split)"

# 匯出訓練用資料
W(train_rows, TRAIN_EXPORT)

# 2) 生成「不與訓練重複」的測試集（stratified 取樣 20%，至少每類 3 筆、最多 80 筆，從 FULL+HC+CB+AUTO 去重後扣掉訓練）
train_keys={norm_key(r["text"]) for r in train_rows}
pool = R(FULL)+R(HC)+R(CB)+R(AUTO)
seen=set(); merged=[]
for r in pool:
    nk=norm_key(r.get("text",""))
    if nk in seen: continue
    seen.add(nk); merged.append(r)

rest=[r for r in merged if norm_key(r["text"]) not in train_keys]
by={}
for r in rest: by.setdefault(r["label"], []).append(r)
test=[]
for lab, arr in by.items():
    n=len(arr)
    if n==0: continue
    take=max(3, min(80, max(1, int(n*0.2))))
    random.shuffle(arr)
    test += arr[:min(take, n)]
W(test, TEST_EXPORT)

# 3) 總結
def dist(rows):
    return dict(Counter([r.get("label","?") for r in rows]))
SUM = []
SUM.append(f"[TRAIN_SRC] {src}")
SUM.append(f"[TRAIN_USED] {len(train_rows)}  dist={dist(train_rows)}")
SUM.append(f"[TEST_AUTO(no-dup)] {len(test)}  dist={dist(test)}")
Path(SUMMARY).write_text("\n".join(SUM)+"\n", encoding="utf-8")
print("\n".join(SUM))
print("[OUT]", TRAIN_EXPORT, TEST_EXPORT, SUMMARY)

# 4) 自動選模型並做一次評測（若有標籤）
cands=[
    "artifacts/intent_svm_plus_auto_cal.pkl",
    "artifacts/intent_svm_plus_auto.pkl",
    "artifacts/intent_svm_plus_clean.pkl",
    "artifacts/intent_svm_plus_boost.pkl",
]
model=None
for c in cands:
    if Path(c).exists(): model=c; break
if model:
    os.system(f'python .sma_tools/eval_only.py --model {model} --input "{TEST_EXPORT}" > "{OUT_DIR}/external_eval_auto.txt" || true')
    print("[EVAL] model=", model, "->", f"{OUT_DIR}/external_eval_auto.txt")
else:
    print("[EVAL] skipped (no model found)")

PY
