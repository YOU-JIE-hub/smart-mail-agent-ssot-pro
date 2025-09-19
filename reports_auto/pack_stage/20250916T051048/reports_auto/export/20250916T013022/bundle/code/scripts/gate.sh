#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"; exec > >(tee -a "$ERR_DIR/run.log") 2>&1
echo "RUN_DIR=$ERR_DIR" > "$ERR_DIR/where.txt"
ok_all=true; reasons=()

# Intent gate
RES="$(ls -1dt reports_auto/eval_fix/2*/tri_results_fixed.json reports_auto/eval/2*/tri_results.json 2>/dev/null | head -n1 || true)"
if [ -n "$RES" ]; then
  PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="$(command -v python)"
  J=$("$PYBIN" - "$RES" <<'PY'
import json, sys
J=json.load(open(sys.argv[1],'r',encoding='utf-8')); runs=J.get("runs",[])
m={r.get("route"):r for r in runs}; ml=m.get("ml") or {}
acc=ml.get("report",{}).get("accuracy",0.0); mf1=ml.get("report",{}).get("macro_f1",0.0)
print(f"{acc} {mf1}")
PY
  )
  ACC=$(echo "$J"|awk '{print $1+0}'); MF1=$(echo "$J"|awk '{print $2+0}')
  if awk "BEGIN{exit !($MF1>=0.92 && $ACC>=0.93)}"; then
    echo "[GATE][INTENT] OK acc=$ACC mf1=$MF1"
  else
    ok_all=false; reasons+=("INTENT acc=${ACC} mf1=${MF1} 未達門檻(acc>=0.93,mf1>=0.92)")
  fi
else
  reasons+=("INTENT 無 tri-eval 結果（跳過）")
fi

# KIE gate（若有金標與評測集，就打 /extract 逐筆比對 phone/amount micro-F1）
if [ -f "${SMA_KIE_GOLD:-}" ] && [ -f "${SMA_KIE_FOR:-}" ]; then
  PORT="${PORT:-$(grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || echo 8000)}"
  PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="$(command -v python)"
  R=$("$PYBIN" - "${SMA_KIE_GOLD}" "${SMA_KIE_FOR}" "$PORT" <<'PY'
import sys, json, requests
gold, pred_in, port = sys.argv[1], sys.argv[2], sys.argv[3]
G=[json.loads(l) for l in open(gold,'r',encoding='utf-8')]
X=[json.loads(l) for l in open(pred_in,'r',encoding='utf-8')]
def fields_ok(f): return {"phone":f.get("phone",""),"amount":f.get("amount","")}
tp=fp=fn=0
for g,x in zip(G,X):
    t=x.get("text","")
    r=requests.post(f"http://127.0.0.1:{port}/extract",json={"texts":[t]}).json()
    pred = r.get("fields",[{}])[0]
    g0 = fields_ok(g); p0 = fields_ok(pred)
    for k in ("phone","amount"):
        y_true = 1 if g0[k] else 0
        y_pred = 1 if p0[k] else 0
        if y_pred==1 and y_true==1: tp+=1
        elif y_pred==1 and y_true==0: fp+=1
        elif y_pred==0 and y_true==1: fn+=1
prec = tp/(tp+fp) if (tp+fp)>0 else 0.0
rec  = tp/(tp+fn) if (tp+fn)>0 else 0.0
f1   = (2*prec*rec)/(prec+rec) if (prec+rec)>0 else 0.0
print(f"{prec} {rec} {f1}")
PY
  ) || R="0 0 0"
  P=$(echo "$R"|awk '{print $1+0}'); Rr=$(echo "$R"|awk '{print $2+0}'); F1=$(echo "$R"|awk '{print $3+0}')
  if awk "BEGIN{exit !($F1>=0.85)}"; then
    echo "[GATE][KIE] OK f1=$F1 (p=$P r=$Rr)"
  else
    ok_all=false; reasons+=("KIE F1=${F1} 未達門檻(F1>=0.85)")
  fi
else
  reasons+=("KIE 無資料（跳過）")
fi

# Spam gate（若有 pkl 就跑極簡 smoke；否則跳過）
if [ -f "${SMA_SPAM_PKL:-}" ]; then
  PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="$(command -v python)"
  S=$("$PYBIN" - "$SMA_SPAM_PKL" <<'PY'
import sys, joblib
mdl=joblib.load(sys.argv[1])
def pick(o):
    if hasattr(o,"predict"): return o
    if isinstance(o,dict):
        for k in ("pipe","pipeline","estimator","model"):
            if k in o and o[k] is not None: return pick(o[k])
    if isinstance(o,(list,tuple)) and o: return pick(o[0])
    raise SystemExit("no predictor")
est=pick(mdl)
X=["🔥限時優惠點此連結","您好，關於上週詢價補充一點資訊"]
y=est.predict(X)
print(",".join(map(str,y)))
PY
  ) || true
  echo "[GATE][SPAM] smoke_pred=$S"
else
  reasons+=("SPAM 無模型（跳過）")
fi

# 統整輸出（不丟非零碼，但印出是否OK與原因）
echo "---- GATE RESULT ----"
if $ok_all; then echo '{"ok":true}'; else echo '{"ok":false,"reasons":['"\"$(IFS=$'\n'; echo "${reasons[*]}" | sed 's/"/\\"/g; s/$/","/' | tr -d '\n' | sed 's/,"$//')"']}' ; fi
exit 0
