#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/bootstrap/${TS}"
LOG="$OUT/run.log"; ERR="$OUT/bootstrap.err"
mkdir -p "$OUT" reports_auto/status scripts vendor
exec > >(tee -a "$LOG") 2>&1
on_err(){ ec=${1:-$?}; { echo "=== BASH_TRAP(bootstrap) ==="; echo "TIME: $(date -Is)"; echo "LAST:${BASH_COMMAND:-<none>}"; echo "CODE:$ec"; } >>"$OUT/last_trace.txt"; echo "exit_code=$ec" > "$ERR"; exit "$ec"; }
on_exit(){ ln -sfn "$OUT" reports_auto/LATEST || true; echo "[*] BOOTSTRAP REPORT: $(cd "$OUT" && pwd)"; if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$OUT")" >/dev/null 2>&1 || true; fi; }
trap 'on_err $?' ERR; trap on_exit EXIT

# 0) 優先復用兄弟專案 venv
if [ ! -e .venv ] && [ -d /home/youjie/projects/smart-mail-agent_ssot/.venv ]; then
  ln -s /home/youjie/projects/smart-mail-agent_ssot/.venv .venv
  echo "[*] .venv -> /home/youjie/projects/smart-mail-agent_ssot/.venv (symlink)"
fi

# 1) 錯誤燈塔：固定輸出最後錯誤路徑
cat > scripts/error_beacon.lib.sh <<'LIB'
beacon_init(){ : "${SMA_BEACON_DIR:=reports_auto}"; mkdir -p "$SMA_BEACON_DIR"; }
beacon_record_run(){ local d="$1"; beacon_init; d="$(cd "$d"&&pwd)"; printf "%s\n" "$d" > "$SMA_BEACON_DIR/LAST_RUN_DIR.txt"; ln -sfn "$d" "$SMA_BEACON_DIR/LATEST" 2>/dev/null||true; command -v wslpath >/dev/null 2>&1 && printf "file://%s\n" "$(wslpath -w "$d")" > "$SMA_BEACON_DIR/LAST_RUN_DIR.winuri" 2>/dev/null||true; }
beacon_record_error(){ local d="$1" e="$2" py="$3"; beacon_init; d="$(cd "$d"&&pwd)"; { echo "RUN_DIR=$d"; echo "ERR_FILE=$d/$(basename "$e")"; echo "PY_LAST=$d/$(basename "$py")"; } > "$SMA_BEACON_DIR/LAST_ERROR_POINTERS.txt"; ln -sfn "$d" "$SMA_BEACON_DIR/LAST_ERROR" 2>/dev/null||true; command -v wslpath >/dev/null 2>&1 && printf "file://%s\n" "$(wslpath -w "$d")" > "$SMA_BEACON_DIR/LAST_ERROR_DIR.winuri" 2>/dev/null||true; }
LIB

# 2) tri_eval_all.sh（v1.6）：自找 Python/自建或復用 venv；單一 .err；全路徑；結束自動開資料夾
cat > scripts/tri_eval_all.sh <<'RUN'
#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
source scripts/error_beacon.lib.sh 2>/dev/null || true

TS="$(date +%Y%m%dT%H%M%S)"
REL_RUN_DIR="reports_auto/eval/${TS}"
RUN_DIR="$(realpath -m "$REL_RUN_DIR" 2>/dev/null || python - <<'PY' "$REL_RUN_DIR"
import os,sys; print(os.path.abspath(sys.argv[1]))
PY
)"
STATUS_DIR="$(realpath -m reports_auto/status 2>/dev/null || echo "$PWD/reports_auto/status")"
LOG="$RUN_DIR/run.log"; ERR="$RUN_DIR/tri_eval.err"; PY_LOG="$RUN_DIR/py_run.log"; PY_LAST="$RUN_DIR/py_last_trace.txt"
mkdir -p "$RUN_DIR" "$STATUS_DIR" reports_auto/.quarantine
: > "$ERR"

print_paths(){ echo "[PATHS]"; echo "  RUN_DIR  = $RUN_DIR"; echo "  LOG     = $LOG"; echo "  ERR     = $ERR"; echo "  PY_LOG  = $PY_LOG"; echo "  PY_LAST = $PY_LAST"; }
on_err(){ c=${1:-$?}; { echo "=== BASH_TRAP ==="; echo "TIME: $(date -Is)"; echo "LAST: ${BASH_COMMAND:-<none>}"; echo "CODE: $c"; } >>"$RUN_DIR/last_trace.txt"; echo "exit_code=$c" > "$ERR"; beacon_record_error "$RUN_DIR" "$ERR" "$PY_LAST"; print_paths; echo "[FATAL] tri-eval failed (code=$c) — see files above"; exit "$c"; }
on_exit(){ ln -sfn "$RUN_DIR" reports_auto/LATEST || true; beacon_record_run "$RUN_DIR"; print_paths; echo "[*] REPORT DIR ready"; if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$RUN_DIR")" >/dev/null 2>&1 || true; fi; }
trap 'on_err $?' ERR; trap on_exit EXIT; trap 'on_err 130' INT; trap 'on_err 143' TERM
{ exec > >(tee -a "$LOG") 2>&1; } || { exec >>"$LOG" 2>&1; }
PS4='+ tri-eval:${LINENO}: '; set -x
echo "[*] tri-eval TS=$TS"; print_paths

# Gate：壞匯入
GATE_TXT="$RUN_DIR/gate_scan.txt"
find . -path './.venv' -prune -o -path './reports_auto' -prune -o -type f \( -name '*.py' -o -name '*.sh' \) -print0 \
| xargs -0 grep -nP 'from\s+pathlib\s+import[^#\n]*\bjson\b' || true | tee "$GATE_TXT"
[ -s "$GATE_TXT" ] && { echo "Gate: bad_import" > "$ERR"; on_err 3; }

# 選 Python：專案 .venv → 兄弟 .venv → PATH python；都沒裝到就本地建立 .venv 並安裝
need_deps_check(){ "$1" - <<'PY' 2>/dev/null
for m in ("numpy","scipy","sklearn","joblib"): __import__(m)
print("OK")
PY
}
PYBIN=""
for cand in "$ROOT/.venv/bin/python" "/home/youjie/projects/smart-mail-agent_ssot/.venv/bin/python" "$(command -v python || true)"; do
  [ -x "$cand" ] || continue
  if need_deps_check "$cand" >/dev/null; then PYBIN="$cand"; break; fi
done
if [ -z "$PYBIN" ]; then
  echo "[INFO] creating local .venv and installing deps (numpy/scipy/sklearn/joblib)"
  python3 -m venv .venv || python -m venv .venv
  . .venv/bin/activate
  PYBIN="$PWD/.venv/bin/python"
  "$PYBIN" -m pip install --upgrade pip >/dev/null
  "$PYBIN" -m pip install -q numpy scipy scikit-learn joblib || { echo "Deps install failed" > "$ERR"; on_err 3; }
  need_deps_check "$PYBIN" >/dev/null || { echo "Deps still missing" > "$ERR"; on_err 3; }
fi
echo "[*] PYBIN=$PYBIN"

# 資料與模型
DATA_INTENT="${DATA_INTENT:-data/intent_eval/dataset.cleaned.jsonl}"
if [ ! -f "$DATA_INTENT" ]; then
  echo "[WARN] dataset missing: $DATA_INTENT -> fallback dataset"
  mkdir -p "$(dirname "$DATA_INTENT")"
  cat > "$RUN_DIR/dataset.min.jsonl" <<'J'
{"text":"您好，想詢問報價與交期，數量100台","label":"biz_quote"}
{"text":"附件服務無法連線，請協助處理","label":"tech_support"}
{"text":"我想了解退訂政策","label":"policy_qa"}
{"text":"發票抬頭需要更新","label":"profile_update"}
J
  DATA_INTENT="$RUN_DIR/dataset.min.jsonl"
fi
: "${SMA_INTENT_ML_PKL:=artifacts/intent_pipeline_aligned.pkl}"
: "${TRI_ENABLE_RULE:=0}"; : "${TRI_ENABLE_ML:=1}"; : "${TRI_ENABLE_OPENAI:=0}"; : "${SMA_DRY_RUN:=1}"

# ZeroPad 垫片
export PYTHONPATH="src:vendor:${PYTHONPATH:-}"
mkdir -p vendor/sma_tools
[ -f vendor/sma_tools/__init__.py ] || echo '__all__=["sk_zero_pad"]' > vendor/sma_tools/__init__.py
[ -f vendor/sma_tools/sk_zero_pad.py ] || cat > vendor/sma_tools/sk_zero_pad.py <<'PY'
from __future__ import annotations
import numpy as np
from scipy import sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin
class ZeroPad(BaseEstimator, TransformerMixin):
    def __init__(self, width:int=1, dtype=np.float64, **kw):
        try: self.width=int(width) if width else 1
        except Exception: self.width=1
        self.dtype=dtype; self._extra=dict(kw)
    def __setstate__(self, state):
        self.__dict__.update(state or {})
        if not hasattr(self,"width"): self.width=1
        if not hasattr(self,"dtype"): self.dtype=np.float64
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((len(X), self.width), dtype=self.dtype)
PY

# 內嵌 Python
"$PYBIN" - "$DATA_INTENT" "$RUN_DIR" "$PY_LOG" "$PY_LAST" <<'PY' || { echo "exec: tri_eval_py" > "$ERR"; on_err 10; }
import os, sys, json, time, traceback, faulthandler, sqlite3
from pathlib import Path
from typing import List
faulthandler.enable(open(sys.argv[3], "w", encoding="utf-8"))
DATA=Path(sys.argv[1]); RUN_DIR=Path(sys.argv[2]); RUN_DIR.mkdir(parents=True, exist_ok=True)
PY_LAST=Path(sys.argv[4])
def last(msg): PY_LAST.write_text(msg, encoding="utf-8")

TRI_RULE=os.getenv("TRI_ENABLE_RULE","0")=="1"
TRI_ML=os.getenv("TRI_ENABLE_ML","1")=="1"
TRI_OAI=os.getenv("TRI_ENABLE_OPENAI","0")=="1"
ML_PKL=os.getenv("SMA_INTENT_ML_PKL",""); DB=Path("reports_auto/audit.sqlite3")

X,y=[],[]
for line in DATA.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    d=json.loads(line); X.append(d.get("text") or d.get("content") or d.get("utterance") or ""); y.append(str(d.get("label") or d.get("intent") or ""))
if not X: last("empty dataset"); sys.exit(2)

def rule_predict(xs:List[str])->List[str]:
    out=[]
    for t in xs:
        t=(t or "").lower()
        if any(k in t for k in ["報價","quote","報價單","價","交期"]): out.append("biz_quote")
        elif any(k in t for k in ["技術","support","無法連線","錯誤"]): out.append("tech_support")
        elif any(k in t for k in ["發票","抬頭"]): out.append("profile_update")
        elif any(k in t for k in ["政策","規則","條款","policy"]): out.append("policy_qa")
        elif any(k in t for k in ["客訴","抱怨","投訴"]): out.append("complaint")
        else: out.append("other")
    return out

def ml_predict(xs:List[str])->List[str]:
    import joblib
    from pathlib import Path as _P
    if not ML_PKL or not _P(ML_PKL).exists(): raise RuntimeError(f"ML PKL not found: {ML_PKL}")
    est=joblib.load(ML_PKL)
    pipe=est if hasattr(est,"predict") else (est.get("pipe") or est.get("pipeline") or est.get("estimator") or est.get("model"))
    if not hasattr(pipe,"predict"): raise RuntimeError("Unsupported estimator container")
    yp=pipe.predict(xs); return [str(v) for v in yp]

def oai_predict(xs:List[str])->List[str]: return ["other"]*len(xs)

from sklearn.metrics import classification_report, confusion_matrix
def cm_labels(y_true,y_pred):
    labels=sorted(set(y_true)|set(y_pred)); cm=confusion_matrix(y_true,y_pred,labels=labels); return labels, cm.tolist()
def eval_one(tag,y_true,y_pred,extra=None):
    rep=classification_report(y_true,y_pred,labels=sorted(set(y_true)|set(y_pred)),output_dict=True,zero_division=0)
    L,CM=cm_labels(y_true,y_pred)
    r={"tag":tag,"n":len(y_true),"labels":L,"report":rep,"confusion_matrix":CM}; r.update(extra or {}); return r

runs=[]
try:
    if TRI_RULE:
        t0=time.perf_counter(); yp=rule_predict(X); dur=int((time.perf_counter()-t0)*1000); runs.append(eval_one("rule.classify",y,yp,{"latency_ms":dur}))
    if TRI_ML:
        t0=time.perf_counter(); yp=ml_predict(X); dur=int((time.perf_counter()-t0)*1000); runs.append(eval_one("ml.classify",y,yp,{"latency_ms":dur,"model":os.path.basename(ML_PKL)}))
    if TRI_OAI:
        t0=time.perf_counter(); yp=oai_predict(X); dur=int((time.perf_counter()-t0)*1000); runs.append(eval_one("openai.classify",y,yp,{"latency_ms":dur}))
except Exception:
    last(traceback.format_exc()); raise

(RUN_DIR/"tri_results.json").write_text(json.dumps({"n":len(X),"runs":runs},ensure_ascii=False,indent=2),encoding="utf-8")

# 可審計：llm_calls（不動核心 schema）
try:
    if DB.exists():
        con=sqlite3.connect(str(DB)); cur=con.cursor()
        for r in runs:
            cur.execute("""INSERT INTO llm_calls(mail_id,stage,model,input_tokens,output_tokens,total_tokens,latency_ms,cost_usd,request_id,created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))""",(None,r["tag"],str(r.get("model") or r["tag"]),0,0,0,int(r.get("latency_ms",0)),0.0,None))
        con.commit(); con.close()
except Exception: pass
PY

# 狀態摘要（遵守 INTENTS_{run.name}.md）
RUN_NAME="$(basename "$RUN_DIR")"
MD="$STATUS_DIR/INTENTS_${RUN_NAME}.md"
{
  echo "# TRI-EVAL ${RUN_NAME}"
  echo "- DATA: $(realpath -m "$DATA_INTENT" 2>/dev/null || echo "$DATA_INTENT")"
  echo "- ML_PKL: $(realpath -m "$SMA_INTENT_ML_PKL" 2>/dev/null || echo "$SMA_INTENT_ML_PKL")"
  echo "- LOG: $LOG"
  echo "- ERR: $ERR"
  echo "- PY_LAST: $PY_LAST"
  echo "- RESULTS: $RUN_DIR/tri_results.json"
} > "$MD"

echo "[DONE] tri-eval OK"; print_paths
RUN

# 3) last_error_show.sh：一鍵印出最後錯誤完整路徑並開資料夾
cat > scripts/last_error_show.sh <<'SHOW'
#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/youjie/projects/smart-mail-agent-ssot-pro
P="reports_auto/LAST_ERROR_POINTERS.txt"
if [ -f "$P" ]; then
  echo "[LAST ERROR POINTERS]"
  cat "$P"
  D="$(grep '^RUN_DIR=' "$P" | sed 's/^RUN_DIR=//')"
  if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$D")" >/dev/null 2>&1 || true; fi
else
  echo "[WARN] 尚無錯誤指標；看 LATEST：$(ls -ld reports_auto/LATEST 2>/dev/null || true)"
fi
SHOW

chmod +x scripts/*.sh

# 4) 立即執行一次 tri-eval；失敗也不會無聲，然後顯示路徑
scripts/tri_eval_all.sh || true
scripts/last_error_show.sh || true
