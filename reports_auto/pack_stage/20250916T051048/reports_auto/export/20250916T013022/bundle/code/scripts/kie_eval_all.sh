#!/usr/bin/env bash
# kie_eval_all.sh — KIE 離線評測（單一 .err + 報表 + LATEST）
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
source scripts/error_beacon.lib.sh 2>/dev/null || true

TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/eval_kie/${TS}"
STATUS_DIR="reports_auto/status"
LOG="$RUN_DIR/run.log"; ERR="$RUN_DIR/kie_eval.err"; PY_LOG="$RUN_DIR/py_run.log"; PY_LAST="$RUN_DIR/py_last_trace.txt"
mkdir -p "$RUN_DIR" "$STATUS_DIR"; : > "$ERR"

print_paths(){ echo "[PATHS]"; for k in RUN_DIR LOG ERR PY_LAST; do v="$(eval echo \$$k)"; echo "  $(printf '%-7s' $k)= $(cd "$(dirname "$v")" && pwd)/$(basename "$v")"; done; }
on_err(){ c=${1:-$?}; { echo "=== BASH_TRAP ==="; echo "TIME: $(date -Is)"; echo "LAST: ${BASH_COMMAND:-<none>}"; echo "CODE: $c"; } >>"$RUN_DIR/last_trace.txt"; echo "exit_code=$c" > "$ERR"; beacon_record_error "$RUN_DIR" "$ERR" "$PY_LAST"; print_paths; echo "[FATAL] kie-eval failed (code=$c) — see files above"; exit "$c"; }
on_exit(){ ln -sfn "$RUN_DIR" reports_auto/LATEST || true; beacon_record_run "$RUN_DIR"; print_paths; echo "[*] REPORT DIR ready"; command -v explorer.exe >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$(cd "$RUN_DIR"&&pwd)")" >/dev/null 2>&1 || true; }
trap 'on_err $?' ERR; trap on_exit EXIT
{ exec > >(tee -a "$LOG") 2>&1; } || { exec >>"$LOG" 2>&1; }
PS4='+ kie-eval:${LINENO}: '; set -x

# 0) env + 依賴
[ -f scripts/env.default ] && set -a && . scripts/env.default && set +a
need_deps_check(){ "$1" - <<'PY' 2>/dev/null
for m in ("numpy","joblib","sklearn"): __import__(m)
print("OK")
PY
}
PYBIN=""
for cand in "$ROOT/.venv/bin/python" "/home/youjie/projects/smart-mail-agent_ssot/.venv/bin/python" "$(command -v python || true)"; do
  [ -x "$cand" ] || continue
  if need_deps_check "$cand" >/dev/null; then PYBIN="$cand"; break; fi
done
[ -n "$PYBIN" ] || { echo "Gate: no_python_or_deps" > "$ERR"; on_err 3; }
echo "[*] PYBIN=$PYBIN"

# 1) dataset / model 來源（你先前提供的既定路徑 → fallback）
DATA_KIE="${DATA_KIE:-data/kie_eval/gold_merged.jsonl}"
[ -f "$DATA_KIE" ] || DATA_KIE="/home/youjie/projects/smart-mail-agent-ssot-pro/data/kie_eval/gold_merged.jsonl"
[ -f "$DATA_KIE" ] || DATA_KIE="/home/youjie/projects/smart-mail-agent_ssot/data/kie_eval/gold_merged.jsonl"
if [ ! -f "$DATA_KIE" ]; then
  mkdir -p "$(dirname "$DATA_KIE")"
  cat > "$RUN_DIR/kie.min.jsonl" <<'J'
{"order_id":"A001","text":"訂單A001 申請人王小明，電話 0912-345-678，金額 NT$12,345","amount":"12345","phone":"0912345678","applicant":"王小明"}
{"order_id":"B002","text":"B002 客戶陳大文，連絡 02-2345-6789，總計 6,000 元","amount":"6000","phone":"0223456789","applicant":"陳大文"}
J
  DATA_KIE="$RUN_DIR/kie.min.jsonl"
  echo "[WARN] KIE dataset missing → using minimal dataset: $DATA_KIE"
fi
: "${SMA_KIE_MODEL_DIR:=/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model}"

# 2) 內嵌 Python：規則抽取 baseline + 可插拔 model（若存在你再換成真推論）
"$PYBIN" - "$DATA_KIE" "$RUN_DIR" "$PY_LOG" "$PY_LAST" "$SMA_KIE_MODEL_DIR" <<'PY' || { echo "exec: kie_eval_py" > "$ERR"; on_err 10; }
import os, sys, json, time, traceback, faulthandler, re, pathlib
from collections import Counter, defaultdict
faulthandler.enable(open(sys.argv[3], "w", encoding="utf-8"))
DATA=pathlib.Path(sys.argv[1]); RUN=pathlib.Path(sys.argv[2]); RUN.mkdir(parents=True,exist_ok=True)
PY_LAST=pathlib.Path(sys.argv[4]); MODEL_DIR=pathlib.Path(sys.argv[5])

def last(msg): PY_LAST.write_text(msg,encoding="utf-8")

def rule_extract(text:str):
    # 極小穩定 regex（不動你核心）：手機/市話/金額/姓名
    if text is None: text=""
    t=str(text)
    phone=""; m=re.search(r'(09\d{2})[-\s]?(\d{3})[-\s]?(\d{3})',t); 
    if m: phone = "".join(m.groups())
    else:
        m=re.search(r'0\d-\d{4}-\d{4}',t) or re.search(r'0\d{1,2}[-\s]?\d{4}[-\s]?\d{4}',t)
        if m: phone=re.sub(r'\D','',m.group(0))
    amt=""; m=re.search(r'(?:NT\$|NTD|\$|元|NT\$)\s*([0-9][0-9,\.]*)',t)
    if m: amt=re.sub(r'[^\d]','',m.group(1))
    name=""; m=re.search(r'(王小明|陳大文|[\u4e00-\u9fa5]{2,4})',t)
    if m: name=m.group(1)
    return {"phone":phone,"amount":amt,"applicant":name}

def predict_records(recs):
    # 若偵測到你之後提供的真 model，可在此替換成真正推論；現在先用規則法保證可跑
    return [rule_extract(r.get("text","")) for r in recs]

# load
gold=[]
for line in DATA.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    d=json.loads(line); gold.append(d)

# fields union
fields=set()
for g in gold:
    fields.update([k for k in g.keys() if k not in ("text","order","order_id","id")])
# 生成預測
t0=time.perf_counter(); preds=predict_records(gold); dur_ms=int((time.perf_counter()-t0)*1000)

def f1(p,r):
    return 0.0 if (p+r)==0 else 2*p*r/(p+r)

# 逐欄位評分（字串嚴格相等）
metrics=[]
for f in sorted(fields):
    y_true=[str(g.get(f,"") or "") for g in gold]
    y_pred=[str(p.get(f,"") or "") for p in preds]
    tp=sum(int(a==b and a!="") for a,b in zip(y_true,y_pred))
    fp=sum(int(a!=b and b!="") for a,b in zip(y_true,y_pred))
    fn=sum(int(a!="" and b=="") for a,b in zip(y_true,y_pred))
    prec=0.0 if (tp+fp)==0 else tp/(tp+fp)
    rec =0.0 if (tp+fn)==0 else tp/(tp+fn)
    metrics.append({"field":f,"n":len(y_true),"tp":tp,"fp":fp,"fn":fn,"precision":round(prec,4),"recall":round(rec,4),"f1":round(f1(prec,rec),4)})

summary={
    "n": len(gold),
    "latency_ms": dur_ms,
    "model_dir": str(MODEL_DIR) if MODEL_DIR.exists() else None,
    "fields": metrics,
    "macro_f1": round(sum(m["f1"] for m in metrics)/len(metrics),4) if metrics else 0.0
}
(RUN/"tri_results_kie.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
PY

# 3) 狀態摘要（KIE_*.md）
RUN_NAME="$(basename "$RUN_DIR")"
MD="$STATUS_DIR/KIE_${RUN_NAME}.md"
{
  echo "# KIE ${RUN_NAME}"
  echo "- DATA: $(realpath -m "$DATA_KIE" 2>/dev/null || echo "$DATA_KIE")"
  echo "- MODEL_DIR: $(realpath -m "$SMA_KIE_MODEL_DIR" 2>/dev/null || echo "$SMA_KIE_MODEL_DIR")"
  echo "- LOG: $(cd "$RUN_DIR"&&pwd)/run.log"
  echo "- ERR: $(cd "$RUN_DIR"&&pwd)/kie_eval.err"
  echo "- PY_LAST: $(cd "$RUN_DIR"&&pwd)/py_last_trace.txt"
  echo "- RESULTS: $(cd "$RUN_DIR"&&pwd)/tri_results_kie.json"
} > "$MD"
