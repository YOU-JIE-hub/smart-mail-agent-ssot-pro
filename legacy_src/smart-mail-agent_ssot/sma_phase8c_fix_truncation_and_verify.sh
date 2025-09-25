#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
[[ -d "$ROOT" ]] || { echo "[FATAL] project root missing: $ROOT" >&2; exit 96; }
cd "$ROOT"

TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/{logs,status} src/smart_mail_agent/pipeline scripts
STATUS="reports_auto/status/PHASE8C_${TS}.md"
LOG="reports_auto/logs/PHASE8C_${TS}.log"

# 落檔同步輸出（避免緩衝）
if command -v stdbuf >/dev/null 2>&1; then
  exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
else
  exec > >(tee -a "$LOG") 2>&1
fi

echo "=== [ENV] ==="
if [[ -x .venv/bin/activate ]]; then . .venv/bin/activate; fi
export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
python -V || true
echo "PYTHONPATH=$PYTHONPATH"
echo

# 1) 修復被截斷的 run_action_handler.py（完整覆寫）
RA="src/smart_mail_agent/pipeline/run_action_handler.py"
[[ -f "$RA" ]] && cp -f "$RA" "$RA.bak.${TS}" || true
cat > "$RA" <<'PY'
from __future__ import annotations
from pathlib import Path
from collections import Counter
import json, time, traceback

from smart_mail_agent.spam.ens import SpamEnsemble
from smart_mail_agent.intent.classifier import IntentRouter
from smart_mail_agent.kie.infer import KIE
from smart_mail_agent.observability.audit_db import ensure_schema, insert_row, write_err_log
from .action_handler import plan_actions

def _now() -> int:
    return int(time.time())

def _safe(fn, stage: str, mail_id: str, meta: dict | None = None):
    t0 = time.perf_counter()
    try:
        out = fn()
        dt = int(1000 * (time.perf_counter() - t0))
        insert_row("metrics", {
            "ts": _now(), "stage": stage, "duration_ms": dt, "ok": 1,
            "extra": json.dumps(meta or {}, ensure_ascii=False),
        })
        return out, None
    except Exception as e:
        tb = traceback.format_exc()
        insert_row("metrics", {
            "ts": _now(), "stage": stage, "duration_ms": 0, "ok": 0,
            "extra": json.dumps({"err": str(e), **(meta or {})}, ensure_ascii=False),
        })
        write_err_log(stage, "ERROR", str(e), {"mail_id": mail_id, "traceback": tb})
        return None, e

def run_e2e_mail(eml_dir: Path, out_root: Path) -> str:
    project_root = Path(__file__).resolve().parents[3]
    ensure_schema()
    out_root.mkdir(parents=True, exist_ok=True)

    # 模型載入（失敗不終止）
    clf_spam, _ = _safe(lambda: SpamEnsemble(project_root), "model/spam", "bootstrap")
    clf_intent, _ = _safe(lambda: IntentRouter(project_root), "model/intent", "bootstrap")
    kie, _       = _safe(lambda: KIE(project_root),          "model/kie",    "bootstrap")

    # 讀入郵件
    cases: list[dict] = []
    for p in sorted(Path(eml_dir).glob("*.eml")):
        mail_id = p.stem
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
            subj, body = "", t
            if "\n\n" in t:
                hdr, body = t.split("\n\n", 1)
                for line in hdr.splitlines():
                    if line.lower().startswith("subject:"):
                        subj = line.split(":", 1)[1].strip()
                        break
            cases.append({"id": mail_id, "subject": subj, "body": body})
            insert_row("mails", {"mail_id": mail_id, "subject": subj, "ts": _now()})
        except Exception as e:
            write_err_log("ingest", "ERROR", f"read {p}: {e}", {"mail_id": mail_id})

    # 推論 + KIE + 規劃
    final: list[dict] = []
    cnt: Counter[str] = Counter()
    for c in cases:
        mail_id = c["id"]
        text = (c.get("subject") or "") + "\n" + (c.get("body") or "")

        # Spam
        y_spam = 0
        if clf_spam:
            y, err = _safe(lambda: clf_spam.predict(text), "spam/predict", mail_id)
            y_spam = int(y == 1) if err is None else 0
        if y_spam == 1:
            cnt["quarantine"] += 1
            final.append({"id": mail_id, "intent": "quarantine", "fields": {}})
            insert_row("actions", {
                "ts": _now(), "mail_id": mail_id, "intent": "quarantine",
                "action": "do_quarantine", "idempotency_key": f"{mail_id}:quarantine",
                "priority": "P1/Sec", "queue": "P1/Sec", "status": "queued"
            })
            continue

        # Intent
        intent = "other"
        if clf_intent:
            lbl, err = _safe(lambda: clf_intent.predict(text), "intent/predict", mail_id)
            intent = (lbl or "other") if err is None else "other"
        cnt[intent] += 1

        # KIE（可選）
        fields = {}
        if kie:
            spans, _ = _safe(lambda: kie.extract(text), "kie/extract", mail_id)
            if spans:
                fields["spans"] = spans

        final.append({"id": mail_id, "intent": intent, "fields": fields})

    # 規劃動作
    _, err = _safe(lambda: plan_actions(final, out_root), "plan/actions", "batch", {"count": len(final)})
    if err is not None:
        write_err_log("plan/actions", "ERROR", "plan_actions failed", {"count": len(final)})

    # 摘要
    lines = ["# E2E SUMMARY", ""]
    for k, v in cnt.items():
        lines.append(f"- {k}: {v}")
    summary = "\n".join(lines) or "ok"
    (out_root / "LATEST_SUMMARY.md").write_text(summary, encoding="utf-8")
    return summary
PY
echo "[OK] Patched $RA"

# 2) 一鍵查看最後錯誤
SHOW="scripts/show_last_crash.sh"
cat > "$SHOW" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
echo "[CRASH] last files:"
ls -1t reports_auto/logs/CRASH_*.log 2>/dev/null | head -n 3 || true
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
echo "[OK] Added $SHOW"

# 3) 可用才跑 pytest；一定跑 e2e_safe（安全封裝）
PT="skip"
if python -c "import pytest" >/dev/null 2>&1; then
  echo "[INFO] Run pytest"
  set +e; python -m pytest -q -rA; PT=$?; set -e
else
  echo "[WARN] pytest not installed; skip tests"
fi

echo "[INFO] Run e2e_safe"
set +e
python -u -X faulthandler -m smart_mail_agent.cli.e2e_safe
EE=$?
set -e
echo "[RESULT] pytest=$PT e2e=$EE"
echo "[HINT] Show last crash: $SHOW"

# 4) 寫審計
{
  echo "# PHASE8C @ ${TS}"
  echo
  echo "## results"
  echo "- pytest: ${PT}"
  echo "- e2e: ${EE}"
  echo
  echo "## files"
  echo "- patched: ${RA}"
  echo "- added: ${SHOW}"
} > "$STATUS"

echo "[DONE] Phase-8C 完成。審計: $STATUS ; 日誌: $LOG"
