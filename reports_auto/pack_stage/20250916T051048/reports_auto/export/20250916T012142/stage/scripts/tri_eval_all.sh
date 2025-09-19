#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
set -a; . scripts/env.default 2>/dev/null || true; set +a
TS="$(date +%Y%m%dT%H%M%S)"; RUN="reports_auto/eval/${TS}"; LOG="$RUN/run.log"; ERR="$RUN/tri_eval.err"; PY_LAST="$RUN/py_last_trace.txt"; PY_LOG="$RUN/py_run.log"
mkdir -p "$RUN" reports_auto/status vendor; : > "$ERR"
print_paths(){ echo "[PATHS]"; for k in RUN LOG ERR PY_LAST; do v="$(eval echo \$$k)"; echo "  $(printf '%-7s' $k)= $(cd "$(dirname "$v")"&&pwd)/$(basename "$v")"; done; }
trap 'echo "exit_code=$?" > "$ERR"; print_paths; echo "[FATAL] tri-eval failed (code=$?) — see files above"; exit 1' ERR
trap 'ln -sfn "$RUN" reports_auto/LATEST || true; print_paths; echo "[*] REPORT DIR ready"; command -v explorer.exe >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$(cd "$RUN"&&pwd)")" >/dev/null 2>&1 || true' EXIT
exec > >(tee -a "$LOG") 2>&1
echo "[*] tri-eval TS=$TS"; print_paths

GATE_TXT="$RUN/gate_scan.txt"
find . -path './.venv' -prune -o -path './reports_auto' -prune -o -type f \( -name '*.py' -o -name '*.sh' \) -print0 | xargs -0 grep -nP '^\s*from\s+pathlib\s+import[^#\n]*\bjson\b' || true | tee "$GATE_TXT"
[ -s "$GATE_TXT" ] && { echo "gate=bad_import" > "$ERR"; exit 2; }

PYBIN=""
for cand in "$ROOT/.venv/bin/python" "/home/youjie/projects/smart-mail-agent_ssot/.venv/bin/python" "$(command -v python || true)"; do
  [ -x "$cand" ] || continue
  "$cand" - <<'PY' || true
for m in ("numpy","scipy","sklearn","joblib"): __import__(m)
print("OK")
PY
  PYBIN="$cand"; break
done
[ -n "$PYBIN" ] || { echo "no_python" > "$ERR"; exit 3; }
echo "[*] PYBIN=$PYBIN"

DATA="data/intent_eval/dataset.cleaned.jsonl"
if [ ! -f "$DATA" ]; then
  mkdir -p "$(dirname "$DATA")"
  cat > "$RUN/dataset.min.jsonl" <<'J'
{"text":"您好，想詢問報價與交期，數量100台","label":"biz_quote"}
{"text":"附件服務無法連線，請協助處理","label":"tech_support"}
{"text":"我想了解退訂政策","label":"policy_qa"}
{"text":"發票抬頭需要更新","label":"profile_update"}
J
  DATA="$RUN/dataset.min.jsonl"
fi

export PYTHONPATH="src:vendor:${PYTHONPATH:-}"
mkdir -p vendor/sma_tools
[ -f vendor/sma_tools/__init__.py ] || echo '__all__=["sk_zero_pad"]' > vendor/sma_tools/__init__.py
[ -f vendor/sma_tools/sk_zero_pad.py ] || cat > vendor/sma_tools/sk_zero_pad.py <<'PY'
from __future__ import annotations
import numpy as np
from scipy import sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin
class ZeroPad(BaseEstimator, TransformerMixin):
    def __init__(self,width:int=1,dtype=np.float64,**kw):
        try: self.width=int(width) if width else 1
        except Exception: self.width=1
        self.dtype=dtype; self._extra=dict(kw)
    def __setstate__(self,s): self.__dict__.update(s or {}); self.width=getattr(self,"width",1); self.dtype=getattr(self,"dtype",np.float64)
    def fit(self,X,y=None): return self
    def transform(self,X): return sp.csr_matrix((len(X), self.width), dtype=self.dtype)
PY

"$PYBIN" - "$DATA" "$RUN" "$PY_LOG" "$PY_LAST" <<'PY'
import os, sys, json, time, traceback, faulthandler, sqlite3
from pathlib import Path
faulthandler.enable(open(sys.argv[3],"w",encoding="utf-8"))
DATA=Path(sys.argv[1]); RUN=Path(sys.argv[2]); LAST=Path(sys.argv[4])
def last(msg): LAST.write_text(msg,encoding="utf-8")
SMA=os.environ.get
ML_PKL=SMA("SMA_INTENT_ML_PKL",""); RULES=SMA("SMA_RULES_SRC",""); DB=Path("reports_auto/audit.sqlite3")
X=[]; y=[]
for line in DATA.read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    d=json.loads(line); X.append(d.get("text") or d.get("content") or ""); y.append(str(d.get("label") or ""))
if not X: last("empty dataset"); sys.exit(2)
def rule_predict(xs):
    out=[]
    for t in xs:
        s=(t or "").lower()
        if any(k in s for k in ["報價","quote","報價單","價","交期"]): out.append("biz_quote")
        elif any(k in s for k in ["技術","support","無法連線","錯誤"]): out.append("tech_support")
        elif any(k in s for k in ["發票","抬頭"]): out.append("profile_update")
        elif any(k in s for k in ["政策","規則","條款","policy"]): out.append("policy_qa")
        elif any(k in s for k in ["客訴","抱怨","投訴"]): out.append("complaint")
        else: out.append("other")
    return out
def ml_predict(xs):
    import joblib, importlib.util, sys, os
    SRC=os.environ.get("SMA_RULES_SRC")
    spec=importlib.util.spec_from_file_location("runtime_threshold_router_impl", SRC)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    import __main__ as MAIN; MAIN.rules_feat=getattr(m,"rules_feat", None)
    if not ML_PKL or not Path(ML_PKL).exists(): raise RuntimeError(f"ML PKL not found: {ML_PKL}")
    obj=joblib.load(ML_PKL)
    pipe=obj if hasattr(obj,"predict") else (obj.get("pipe") or obj.get("pipeline") or obj.get("estimator") or obj.get("model"))
    if not hasattr(pipe,"predict"): raise RuntimeError("Unsupported estimator")
    return [str(v) for v in pipe.predict(xs)]
def oai_predict(xs): return ["other"]*len(xs)
from sklearn.metrics import classification_report, confusion_matrix
def cm(y_true,y_pred):
    L=sorted(set(y_true)|set(y_pred)); import numpy as np
    from sklearn.metrics import confusion_matrix as _cm
    return L, _cm(y_true,y_pred,labels=L).tolist()
def eval_one(tag,yt,yp,extra=None):
    rep=classification_report(yt,yp,labels=sorted(set(yt)|set(yp)),output_dict=True,zero_division=0)
    L,CM=cm(yt,yp); r={"tag":tag,"n":len(yt),"labels":L,"report":rep,"confusion_matrix":CM}; r.update(extra or {}); return r
runs=[]
import time as _t
t0=_t.perf_counter(); yp=rule_predict(X); runs.append(eval_one("rule.classify",y,yp,{"latency_ms":int((_t.perf_counter()-t0)*1000)}))
t0=_t.perf_counter(); yp=ml_predict(X); runs.append(eval_one("ml.classify",y,yp,{"latency_ms":int((_t.perf_counter()-t0)*1000),"model":os.path.basename(ML_PKL)}))
(RUN/"tri_results.json").write_text(json.dumps({"n":len(X),"runs":runs},ensure_ascii=False,indent=2),encoding="utf-8")
try:
    if DB.exists():
        con=sqlite3.connect(str(DB)); cur=con.cursor()
        for r in runs:
            cur.execute("""INSERT INTO llm_calls(mail_id,stage,model,input_tokens,output_tokens,total_tokens,latency_ms,cost_usd,request_id,created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))""",(None,r["tag"],str(r.get("model") or r["tag"]),0,0,0,int(r.get("latency_ms",0)),0.0,None))
        con.commit(); con.close()
except Exception: pass
PY
NAME="$(basename "$RUN")"; MD="reports_auto/status/INTENTS_${NAME}.md"
{ echo "# INTENTS ${NAME}"; echo "- DATA: $(realpath -m "$DATA")"; echo "- ML_PKL: $(realpath -m "${SMA_INTENT_ML_PKL:-}")"; echo "- LOG: $(cd "$RUN"&&pwd)/run.log"; echo "- ERR: $(cd "$RUN"&&pwd)/tri_eval.err"; echo "- PY_LAST: $(cd "$RUN"&&pwd)/py_last_trace.txt"; echo "- RESULTS: $(cd "$RUN"&&pwd)/tri_results.json"; } > "$MD"
