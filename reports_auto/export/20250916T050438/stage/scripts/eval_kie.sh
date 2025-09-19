#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-$(grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || echo 8000)}"
GOLD="/home/youjie/projects/smart-mail-agent_ssot/data/kie_eval/gold_merged.jsonl"
ALT="/home/youjie/projects/smart-mail-agent_ssot/data/kie/test_real.for_eval.jsonl"
OUTDIR="reports_auto/kie_eval/$(date +%Y%m%dT%H%M%S)"; mkdir -p "$OUTDIR"
OUT="$OUTDIR/report.json"

pick_data(){
  if [ -f "$GOLD" ]; then echo "$GOLD"; elif [ -f "$ALT" ]; then echo "$ALT"; else echo ""; fi
}
DATA="$(pick_data)"
if [ -z "$DATA" ]; then
  echo '{"status":"SKIPPED","reason":"no kie dataset"}' > "$OUT"
  echo "[WARN] KIE eval skipped (dataset missing) -> $OUT"
  exit 0
fi

python - <<'PY' "$DATA" "$OUT" "$PORT"
import sys, json, urllib.request
from sklearn.metrics import precision_recall_fscore_support
import numpy as np

path, out, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
def load_jsonl(p):
    xs=[]
    with open(p,"r",encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: xs.append(json.loads(line))
            except: xs.append({"text":line})
    return xs

def get_text(o):
    for k in ("text","content","msg","body"): 
        if k in o: return str(o[k])
    return str(o)

def get_gt(o):
    # 支援 {"fields":{"phone":"..","amount":".."}} 或扁平欄位
    if isinstance(o,dict) and "fields" in o and isinstance(o["fields"],dict):
        d=o["fields"]
    else:
        d={k.lower():str(o[k]) for k in o.keys() if k.lower() in ("phone","amount")}
    phone = d.get("phone","") or ""
    amount = d.get("amount","") or ""
    # 正規化
    phone = "".join(ch for ch in phone if ch.isdigit())
    amount = "".join(ch for ch in amount if ch.isdigit())
    return {"phone":phone, "amount":amount}

def batched(lst, n=32):
    for i in range(0, len(lst), n): yield lst[i:i+n]

def extract_batch(texts):
    payload = json.dumps({"texts":texts}).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/extract", data=payload, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")).get("fields",[])
    
xs=load_jsonl(path)
texts=[get_text(o) for o in xs]
gts=[get_gt(o) for o in xs]

preds=[]
for chunk in batched(texts, 64):
    preds.extend(extract_batch(chunk))

def bin_match(gt, pr):
    # 精確匹配 (空值也計入)
    return int( (gt or "") == (pr or "") )

fields=("phone","amount")
scores={}
for f in fields:
    y_true=[ (g or "") for g in (d.get(f,"") for d in gts) ]
    y_pred=[ (p or "") for p in (d.get(f,"") for d in preds)]
    # 將非空視為正類（用於 PRF1），另計 exact-match rate
    y_t=[1 if v else 0 for v in y_true]
    y_p=[1 if v else 0 for v in y_pred]
    p,r,f1,_=precision_recall_fscore_support(y_t, y_p, average="binary", zero_division=0)
    exact = np.mean([bin_match(t,p) for t,p in zip(y_true,y_pred)]) if y_true else 0.0
    scores[f]={"presence_P":float(p),"presence_R":float(r),"presence_F1":float(f1),"exact_rate":float(exact)}

macro_f1 = float(np.mean([scores[f]["presence_F1"] for f in fields]))
rep={"n":len(xs),"fields":scores,"macro_presence_F1":macro_f1}
json.dump(rep, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(out)
PY
echo "[OK] KIE report -> $OUT"
