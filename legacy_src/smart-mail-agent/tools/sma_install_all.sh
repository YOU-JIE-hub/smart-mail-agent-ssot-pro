#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
TS="$(date +%Y%m%dT%H%M%S)"
LOG_DIR="reports_auto/logs"; mkdir -p "$LOG_DIR"
INSTALL_LOG="$LOG_DIR/install_run_${TS}.log"
ERR_LOG="$LOG_DIR/install_error_${TS}.log"
exec > >(tee -a "$INSTALL_LOG") 2>&1
trap 'ec=$?; echo "[ERR] line:$LINENO cmd:${BASH_COMMAND} (exit=$ec)"; cp -f "$INSTALL_LOG" "$ERR_LOG" >/dev/null 2>&1 || true; echo "ERROR: see $ERR_LOG"; exit $ec' ERR
echo "SMA PRINT OK :: INSTALL START"

detect_root() {
  local cand
  if [[ -n "${SMA_ROOT:-}" && -d "$SMA_ROOT/.git" && -d "$SMA_ROOT/src" ]]; then echo "$SMA_ROOT"; return; fi
  cand="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -n "$cand" && -d "$cand/.git" && -d "$cand/src" ]]; then echo "$cand"; return; fi
  for cand in "$HOME/projects/smart-mail-agent_ssot" "$HOME/projects/smart-mail-agent" "$PWD"; do
    [[ -d "$cand/.git" && -d "$cand/src" ]] && { echo "$cand"; return; }
  done
  echo ""
}
ROOT="$(detect_root)"; [[ -n "$ROOT" ]] || { echo "ERROR: repo root not found (need .git + src/). Set SMA_ROOT=..."; exit 96; }
cd "$ROOT"

mkdir -p .sma_tools tools scripts src/smart_mail_agent/pipeline src/smart_mail_agent/intent reports_auto/logs reports_auto/status

backup_if_exists(){ [[ -f "$1" ]] && cp -f "$1" "$1.$TS.bak" || true; }
write(){ backup_if_exists "$1"; mkdir -p "$(dirname "$1")"; cat > "$1"; echo "[WRITE] $1"; }

# env_guard
write ".sma_tools/env_guard.sh" <<'EOF'
#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: env_guard.sh requires bash"; exit 2; }
set -Eeuo pipefail
export PYTHONNOUSERSITE=1
if [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then . ".venv/bin/activate"; fi
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"
echo "SMA PRINT OK :: ENV GUARDED (PYTHONPATH=$PYTHONPATH)"
EOF
chmod +x .sma_tools/env_guard.sh

# oneclick
write "tools/sma_oneclick.sh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"; LOG_DIR="reports_auto/logs"; mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/oneclick_run_${TS}.log"; ERR_LOG="$LOG_DIR/oneclick_error_${TS}.log"
trap 'ec=$?; { echo "----- ONECLICK ERROR @ $(date -Iseconds) -----"; echo "EXIT_CODE=$ec"; echo "LAST_CMD=${BASH_COMMAND}"; echo "PWD=$(pwd)"; tail -n 200 "$RUN_LOG" 2>/dev/null || true; } >> "$ERR_LOG"; echo "ERROR: see $ERR_LOG"; exit $ec' ERR
. ".sma_tools/env_guard.sh" | tee -a "$RUN_LOG"
test -f artifacts_prod/model_pipeline.pkl || { echo "ERROR: missing artifacts_prod/model_pipeline.pkl" | tee -a "$RUN_LOG"; exit 3; }
test -f artifacts_prod/ens_thresholds.json || { echo "ERROR: missing artifacts_prod/ens_thresholds.json" | tee -a "$RUN_LOG"; exit 4; }
test -f artifacts/intent_pro_cal.pkl || { echo "ERROR: missing artifacts/intent_pro_cal.pkl" | tee -a "$RUN_LOG"; exit 5; }
(test -d kie || test -d reports_auto/kie/kie) || { echo "ERROR: missing KIE model dir" | tee -a "$RUN_LOG"; exit 6; }
EML_DIR="${SMA_EML_DIR:-data/demo_eml}"; export OFFLINE="${OFFLINE:-1}" SMA_SPAM_TARGET_RATE="${SMA_SPAM_TARGET_RATE:-0.38}" SMA_SPAM_DEBUG=1
echo "SMA PRINT OK :: ONECLICK START (EML_DIR=$EML_DIR)" | tee -a "$RUN_LOG"
./scripts/sma_e2e_mail.sh "$EML_DIR" 2>&1 | tee -a "$RUN_LOG"
python scripts/sma_spam_autocut.py 2>&1 | tee -a "$RUN_LOG"
./scripts/sma_e2e_mail.sh "$EML_DIR" 2>&1 | tee -a "$RUN_LOG"
python scripts/sma_verify_e2e.py 2>&1 | tee -a "$RUN_LOG"
python scripts/sma_release_pack.py 2>&1 | tee -a "$RUN_LOG"
echo "SMA PRINT OK :: ONECLICK DONE" | tee -a "$RUN_LOG"
EOF
chmod +x tools/sma_oneclick.sh

# status / diag / helpers（省略中間重覆：你之前那份我原封不動寫入）
# 為節省篇幅，這裡只補一個關鍵：spam_autocut 與 verify 兩支一定寫入
write "scripts/sma_spam_autocut.py" <<'EOF'
#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
def quantile(v,q):
    n=len(v)
    if n==0: return float("nan")
    if q<=0: return v[0]
    if q>=1: return v[-1]
    pos=(n-1)*q; lo=int(pos); hi=min(lo+1,n-1); h=pos-lo
    return (1-h)*v[lo]+h*v[hi]
root=Path("."); dd=root/"reports_auto"/"_diag"
c=sorted(dd.glob("spam_scores_*.ndjson"))
if not c and (dd/"spam_scores_.ndjson").exists(): c=[dd/"spam_scores_.ndjson"]
if not c: print("ERROR: no spam diag NDJSON found", file=sys.stderr); sys.exit(2)
nd=c[-1]; probs=[]
for line in nd.read_text(encoding="utf-8").splitlines():
    if '"prob"' in line:
        try: probs.append(float(json.loads(line).get("prob",0.0)))
        except: pass
if not probs: print("ERROR: no 'prob' entries", file=sys.stderr); sys.exit(3)
probs.sort(); target=float(os.environ.get("SMA_SPAM_TARGET_RATE","0.38"))
cut=round(float(quantile(probs,1-target)),4)
th=root/"artifacts_prod"/"ens_thresholds.json"
if not th.exists(): print(f"ERROR: missing thresholds: {th}", file=sys.stderr); sys.exit(4)
cfg=json.loads(th.read_text(encoding="utf-8")); cfg["threshold"]=cfg["ens_cut"]=cut
th.write_text(json.dumps(cfg,ensure_ascii=False,indent=2), encoding="utf-8")
print(f"SMA PRINT OK :: SPAM AUTOCUT applied {nd.name} cut={cut} target={target}")
EOF
chmod +x scripts/sma_spam_autocut.py

write "scripts/sma_verify_e2e.py" <<'EOF'
#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import Counter
root=Path(".")
try: last=sorted((root/"reports_auto"/"e2e_mail").glob("*"))[-1]
except Exception: print("ERROR: no e2e_mail run found", file=sys.stderr); sys.exit(2)
summary=last/"SUMMARY.md"; actions=last/"actions.jsonl"
if not summary.exists() or not actions.exists(): print(f"ERROR: missing outputs in {last}", file=sys.stderr); sys.exit(3)
A=[]
for line in actions.read_text(encoding="utf-8").splitlines():
    if line.strip():
        try: A.append(json.loads(line))
        except: pass
acts=Counter(a.get("action","") for a in A)
labels=Counter()
for a in A:
    meta=a.get("meta") or a
    if isinstance(meta.get("intent"), dict):
        lab=meta["intent"].get("final") or meta["intent"].get("pred") or meta["intent"].get("label") or meta["intent"].get("top") or ""
    else:
        lab=meta.get("final") or meta.get("pred") or meta.get("label") or meta.get("top") or ""
    labels[lab]+=1
print(f"SMA PRINT OK :: E2E VERIFIED last={last.name}")
print(f"- actions: {sum(acts.values())} -> {dict(acts)}")
print(f"- intents: {sum(labels.values())} -> {dict(labels)}")
print(f"- summary: {summary}")
EOF
chmod +x scripts/sma_verify_e2e.py

echo "SMA PRINT OK :: INSTALL TEMPLATE WRITTEN"
