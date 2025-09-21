#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || { echo "[FATAL] $ROOT"; exit 2; }
[[ -d .venv ]] || python3 -m venv .venv; . .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}" TOKENIZERS_PARALLELISM=false
mkdir -p reports_auto/{logs,diagnostics,alignment} .sma_tools
TS="$(date +%Y%m%dT%H%M%S)"; LOG="reports_auto/logs/diag_align_${TS}.log"
ln -sf "$(basename "$LOG")" reports_auto/logs/latest.log || true
exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
PS4='+ [\t] ' ; set -x
trap 'ec=$?; echo "[ERROR] exit=$ec line:$LINENO cmd:${BASH_COMMAND}";
      tail -n 200 "$LOG" > "reports_auto/diagnostics/LAST_TAIL_${TS}.log" || true;
      printf "exit=%s\ncmd=%s\n" "$ec" "${BASH_COMMAND}" > "reports_auto/diagnostics/LAST_CAUSE_${TS}.txt";
      exit 0' ERR

CAUSE="reports_auto/diagnostics/ALIGN_CRASH_CAUSE_${TS}.md"
{
  echo "# ALIGN Crash Cause Report"
  echo "- time: $(date -Iseconds)"
  echo "- python: $(python -V 2>&1)"
  echo "- regex installed: $(pip show regex >/dev/null 2>&1 && echo yes || echo no)"
} > "$CAUSE"

A=".sma_tools/align_gold_to_pred.py"
if [[ ! -f "$A" ]]; then
  {
    echo
    echo "## Root cause: align script missing"
    echo "- Not found: $A"
  } >> "$CAUSE"
else
  if grep -n "\\\\p{" "$A" >/dev/null 2>&1; then
    echo -e "\n## Root cause: unsupported '\\p{…}' in Python re" >> "$CAUSE"
  fi
  python - <<'PY'
import py_compile
py_compile.compile(".sma_tools/align_gold_to_pred.py", doraise=True)
print("[PY_COMPILE] OK")
PY
fi

PRED="reports_auto/predict_all.jsonl"; G_INT="data/intent/test_labeled.jsonl"; G_SP="data/spam/test_labeled.jsonl"
python - <<'PY'
import json,re,unicodedata,pathlib
def load(p):
    out=[]; pth=pathlib.Path(p)
    if not pth.exists(): print(f"[NOT_FOUND] {p}"); return out
    with open(p,encoding="utf-8",errors="ignore") as f:
        for i,ln in enumerate(f,1):
            ln=ln.strip()
            if not ln: continue
            try: out.append(json.loads(ln))
            except Exception as e: print(f"[BAD_JSONL] {p}:{i} {e}")
    return out
def norm(s):
    if s is None: return ""
    s=unicodedata.normalize("NFKC",str(s)).replace("\u3000"," ").lower()
    return re.sub(r"\s+"," ",s).strip()
def extract(o):
    parts=[]
    for k in ("subject","title","content","body","text","plain","raw_text","snippet","summary","description","text_norm","body_norm"):
        v=o.get(k)
        if isinstance(v,str): parts.append(v)
    for kk in ("src","source","email","payload","data"):
        v=o.get(kk)
        if isinstance(v,dict):
            for k in ("subject","title","content","body","text","plain","raw_text","snippet","summary","description","text_norm","body_norm"):
                vv=v.get(k)
                if isinstance(vv,str): parts.append(vv)
    return norm("\n".join(parts))
pred=load("reports_auto/predict_all.jsonl")
gint=load("data/intent/test_labeled.jsonl")
gsp =load("data/spam/test_labeled.jsonl")
def stat(name,arr):
    n=len(arr); miss_id=sum(1 for o in arr if not (o.get("id") or "") )
    empty=sum(1 for o in arr if not extract(o))
    print(f"[STAT] {name}: n={n} miss_id={miss_id} empty_text={empty}")
stat("pred",pred); 
if gint: stat("gold_intent",gint)
if gsp : stat("gold_spam",gsp)
PY

if [[ -f "$G_INT" && -f "$PRED" ]]; then
  head -n 50 "$G_INT" > reports_auto/alignment/_gold_head50.jsonl || true
  set +e
  PYTHONFAULTHANDLER=1 python -X dev -u .sma_tools/align_gold_to_pred.py \
    --gold reports_auto/alignment/_gold_head50.jsonl \
    --pred "$PRED" \
    --out  reports_auto/alignment/_diag_head50.csv \
    --mode auto --fuzzy_threshold 0.90
  RC=$?; set -e
  echo -e "\n## Execution\n- RC: $RC" >> "$CAUSE"
fi

{
  echo -e "\n## Log tail\n"
  tail -n 120 "$LOG" || true
} >> "$CAUSE"

echo "[WRITE] $CAUSE"

DIAG="reports_auto/diagnostics"
if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$PWD/$DIAG")" || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$DIAG" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$DIAG" || true
fi
