#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/{logs,status} src/smart_mail_agent/pipeline scripts
STATUS="reports_auto/status/PHASE8B_${TS}.md"
LOG="reports_auto/logs/PHASE8B_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

# 0) venv / env
if [[ -x .venv/bin/activate ]]; then . .venv/bin/activate; fi
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python -V || true

# 1) 強化流水線：單封錯誤不影響整體、每步落 DB/LOG
RA="src/smart_mail_agent/pipeline/run_action_handler.py"
cp -f "$RA" "${RA}.bak.${TS}" 2>/dev/null || true
cat > "$RA" <<'PY'
from __future__ import annotations
from pathlib import Path
from collections import Counter
import time, json, traceback

from smart_mail_agent.spam.ens import SpamEnsemble
from smart_mail_agent.intent.classifier import IntentRouter
from smart_mail_agent.kie.infer import KIE
from smart_mail_agent.observability import insert_row, write_err_log, ensure_schema
from .action_handler import plan_actions

def _now() -> int: return int(time.time())

def _safe(fn, stage: str, mail_id: str, **kw):
    try:
        t0=time.perf_counter()
        out = fn()
        dt=int(1000*(time.perf_counter()-t0))
        insert_row("metrics", {"ts":_now(), "stage":stage, "duration_ms":dt, "ok":1, "extra":json.dumps(kw, ensure_ascii=False)})
        return out, None
    except Exception as e:
        tb = traceback.format_exc()
        insert_row("metrics", {"ts":_now(), "stage":stage, "duration_ms":0, "ok":0, "extra":json.dumps({"err":str(e)}, ensure_ascii=False)})
        write_err_log(stage, "ERROR", f"{e}", {"mail_id":mail_id, "traceback":tb})
        return None, e

def run_e2e_mail(eml_dir: Path, out_root: Path) -> str:
    project_root = Path(__file__).resolve().parents[3]
    ensure_schema()  # 確保 DB 存在
    out_root.mkdir(parents=True, exist_ok=True)

    # 準備模型
    (clf_spam, err1) = _safe(lambda: SpamEnsemble(project_root), "model/spam", "bootstrap")
    (clf_intent, err2) = _safe(lambda: IntentRouter(project_root), "model/intent", "bootstrap")
    (kie, err3) = _safe(lambda: KIE(project_root), "model/kie", "bootstrap")

    cases=[]; errs=[]
    for p in sorted(Path(eml_dir).glob("*.eml")):
        mail_id = p.stem
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
            subj, body = "", t
            if "\n\n" in t:
                hdr, body = t.split("\n\n",1)
                for line in hdr.splitlines():
                    if line.lower().startswith("subject:"):
                        subj=line.split(":",1)[1].strip(); break
            cases.append({"id":mail_id, "subject":subj, "body":body})
            insert_row("mails", {"mail_id":mail_id, "subject":subj, "ts":_now()})
        except Exception as e:
            write_err_log("ingest", "ERROR", f"read {p}: {e}", {"mail_id":mail_id})
            errs.append((mail_id, "ingest", str(e)))

    final=[]; cnt=Counter()
    for c in cases:
        mail_id = c["id"]
        text = (c.get("subject") or "") + "\n" + (c.get("body") or "")

        # 1) Spam
        y_spam = 0
        if clf_spam:
            (proba, e) = _safe(lambda: clf_spam.predict(text), "spam/predict", mail_id)
            if e: y_spam = 0
            else: y_spam = int(proba==1)
        if y_spam==1:
            cnt["spam"]+=1
            final.append({"id":mail_id,"intent":"quarantine","fields":{}})
            insert_row("actions", {"ts":_now(), "mail_id":mail_id, "intent":"quarantine", "action":"do_quarantine", "idempotency_key": f"{mail_id}:quarantine", "priority":"P1/Sec", "queue":"P1/Sec", "status":"queued"})
            continue

        # 2) Intent
        intent="other"
        if clf_intent:
            (lbl, e) = _safe(lambda: clf_intent.predict(text), "intent/predict", mail_id)
            intent = lbl or "other" if not e else "other"
        cnt[intent]+=1

        # 3) KIE（不阻斷）
        fields={}
        if kie:
            (spans, _) = _safe(lambda: kie.extract(text), "kie/extract", mail_id)
            if spans: fields["spans"]=spans

        final.append({"id":mail_id,"intent":intent,"fields":fields})

    # 4) 規劃動作（任何錯都記錄，不讓整體崩）
    (none, e) = _safe(lambda: plan_actions(final, out_root), "plan/actions", "batch")
    if e:
        write_err_log("plan/actions", "ERROR", "plan_actions failed", {"count":len(final)})

    # 5) 輸出摘要
    summary_lines=["# E2E SUMMARY","","Counts:"]
    for k,v in cnt.items(): summary_lines.append(f"- {k}: {v}")
    summary = "\n".join(summary_lines) or "ok"
    (out_root/"LATEST_SUMMARY.md").write_text(summary, encoding="utf-8")
    return summary
PY

# 2) 一鍵查看最後錯誤的小工具
SHOW="scripts/show_last_crash.sh"
cat > "$SHOW" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd "${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
echo "[CRASH] last files:"
ls -1t reports_auto/logs/CRASH_*.log 2>/dev/null | head -n 3
echo
f="$(ls -1t reports_auto/logs/CRASH_*.log 2>/dev/null | head -n1 || true)"
if [[ -n "${f:-}" && -f "$f" ]]; then
  echo "--- tail -n 400 $f ---"
  tail -n 400 "$f"
fi
echo
if [[ -f reports_auto/logs/pipeline.ndjson ]]; then
  echo "--- tail -n 80 pipeline.ndjson ---"
  tail -n 80 reports_auto/logs/pipeline.ndjson
fi
SH
chmod +x "$SHOW"

# 3) Smoke + 驗收
set +e
python -m pytest -q -rA
PT=$?
python -u -X faulthandler -m smart_mail_agent.cli.e2e_safe
EE=$?
set -e

{
  echo "# PHASE8B @ ${TS}"
  echo
  echo "## result"
  echo "- pytest exit: ${PT}"
  echo "- e2e exit: ${EE}"
  echo
  echo "## files"
  echo "- patched: ${RA}"
  echo "- added: ${SHOW}"
} > "$STATUS"

echo
echo "[HINT] 檢視最後錯誤：$SHOW"
echo "[DONE] Phase-8B（never-die e2e + full DB/LOG）完成。審計: $STATUS ; 日誌: $LOG"
