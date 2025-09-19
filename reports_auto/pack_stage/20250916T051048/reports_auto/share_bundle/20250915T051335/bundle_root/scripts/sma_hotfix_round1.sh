#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

# 確保 Python 能匯入 scripts/hotfix/*
export PYTHONPATH="scripts:${PYTHONPATH:-}"

# 先做後處理（會自動找最新那批輸出）
python3 -u scripts/hotfix/postprocess_latest.py

# 再由殼層挑出「真的最新」的那一批做稽核，並刷新 LATEST
ROOT="reports_auto/e2e_mail"
if [[ -x scripts/sma__pick_latest.sh ]]; then
  LAST="$(bash scripts/sma__pick_latest.sh)"
else
  LAST="$(ls -1dt "$ROOT"/20* 2>/dev/null | head -n1 || true)"
fi

if [[ -z "${LAST:-}" || ! -d "$LAST" ]]; then
  echo "[ERR] Cannot determine LAST under $ROOT" >&2
  exit 1
fi

ln -sfn "$(readlink -f "$LAST")" "$ROOT/LATEST"

echo
echo "== Quick audit =="
jq -r '.status' "$LAST/actions.jsonl" | sort | uniq -c || true

echo
echo "-- non-ok (from patched) --"
if [[ -f "$LAST/actions.patched.jsonl" ]]; then
  jq -r 'select(.status!="ok")
   | [.case_id,.action_type//.action,.status, (.reason // .error // .note // "n/a"), (.outbox_path_actual // .outbox_path // "n/a")]
   | @tsv' "$LAST/actions.patched.jsonl" | column -ts$'\t' || true
else
  echo "(no patched actions found: $LAST/actions.patched.jsonl)"
fi

echo
echo "-- outbox files --"
if [[ -d "$LAST/rpa_out/email_outbox" ]]; then
  find "$LAST/rpa_out/email_outbox" -maxdepth 1 -type f -name '*.eml' | sed "s|$LAST/||" | sort | head -n 50
else
  echo "(no outbox dir)"
fi

echo
echo "[INFO] LAST path: $LAST"
echo "[INFO] LATEST -> $(readlink -f "$ROOT/LATEST" 2>/dev/null || echo 'n/a')"
