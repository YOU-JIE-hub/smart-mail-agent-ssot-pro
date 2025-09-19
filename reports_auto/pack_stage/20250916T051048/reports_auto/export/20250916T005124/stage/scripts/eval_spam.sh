#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
SPAM_PKL="/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl"
OUTDIR="reports_auto/spam_eval/$(date +%Y%m%dT%H%M%S)"; mkdir -p "$OUTDIR"
OUT="$OUTDIR/report.json"

if [ ! -f "$SPAM_PKL" ]; then
  echo '{"status":"SKIPPED","reason":"spam model missing"}' > "$OUT"
  echo "[WARN] Spam eval skipped (model missing) -> $OUT"; exit 0
fi

# 嘗試尋找 jsonl 標註資料（欄位 text+label/labels in {spam,ham}）
CAND1="/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/gold.jsonl"
CAND2="data/spam_eval/gold.jsonl"
DATA=""
for p in "$CAND1" "$CAND2"; do [ -f "$p" ] && DATA="$p" && break; done

if [ -z "$DATA" ]; then
  # 無資料 -> 只做載入與數句 smoke，評測略過
  python - <<'PY' "$SPAM_PKL" "$OUT"
import sys, json, joblib
pkl, out = sys.argv[1], sys.argv[2]
try:
    obj=joblib.load(pkl)
    pipe = obj if hasattr(obj,"predict") else obj.get("pipe") or obj.get("pipeline")
    ys = pipe.predict(["hi", "limited time offer!!!", "免費 中獎 點我領取"])
    json.dump({"status":"SMOKE","pred":list(map(str,ys))}, open(out,"w",encoding="utf-8"))
    print(out)
except Exception as e:
    json.dump({"status":"ERROR","error":str(e)}, open(out,"w",encoding="utf-8"))
    print(out)
PY
  echo "[WARN] Spam eval data missing, smoke only -> $OUT"; exit 0
fi

python - <<'PY' "$SPAM_PKL" "$OUT" "$DATA"
import sys, json, joblib
from sklearn.metrics import classification_report, accuracy_score
pkl, out, data = sys.argv[1], sys.argv[2], sys.argv[3]
def load_jsonl(p):
    xs=[]
    with open(p,"r",encoding="utf-8") as f:
        for line in f:
            if line.strip():
                xs.append(json.loads(line))
    return xs
def get_text(o):
    for k in ("text","content","msg","body"): 
        if k in o: return str(o[k])
    return str(o)
def get_label(o):
    for k in ("label","labels","y"): 
        if k in o:
            v=o[k]; 
            if isinstance(v,(list,tuple)): v=v[0] if v else "ham"
            return str(v)
    return "ham"
xs=load_jsonl(data)
X=[get_text(o) for o in xs]
Y=[get_label(o).lower() for o in xs]
obj=joblib.load(pkl)
pipe = obj if hasattr(obj,"predict") else obj.get("pipe") or obj.get("pipeline")
yp=list(map(lambda s:str(s).lower(), pipe.predict(X)))
rep=classification_report(Y, yp, labels=["ham","spam"], zero_division=0, output_dict=True)
acc=accuracy_score(Y, yp)
json.dump({"n":len(X),"accuracy":acc,"report":rep}, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(out)
PY
echo "[OK] Spam report -> $OUT"
