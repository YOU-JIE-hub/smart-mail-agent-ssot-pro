#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"

port_from_env(){ grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || true; }

LAST_ONECLICK="$(ls -1dt reports_auto/oneclick/2* 2>/dev/null | head -n1 || true)"
LAST_API="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
LAST_EVAL="$(ls -1dt reports_auto/eval/2* 2>/dev/null | head -n1 || true)"
PORT="${PORT:-$(port_from_env)}"; [ -n "$PORT" ] || PORT=8000

echo "[WHERE]"
[ -n "$LAST_ONECLICK" ] && echo "  ONECLICK = $(cd "$LAST_ONECLICK" && pwd)" || echo "  ONECLICK = <none>"
[ -n "$LAST_API" ] && echo "  API      = $(cd "$LAST_API" && pwd)" || echo "  API      = <none>"
[ -n "$LAST_EVAL" ] && echo "  EVAL     = $(cd "$LAST_EVAL" && pwd)" || echo "  EVAL     = <none>"
echo "  PORT     = $PORT"

echo
echo "=== ONECLICK ==="
if [ -n "$LAST_ONECLICK" ]; then
  OERR="$LAST_ONECLICK/oneclick.err"
  [ -f "$OERR" ] && { echo "[oneclick.err] $OERR"; sed -n '1,200p' "$OERR"; } || echo "(no oneclick.err)"
  ORUN="$LAST_ONECLICK/run.log"
  [ -f "$ORUN" ] && { echo "[oneclick.run.log] $ORUN (tail-200)"; tail -n 200 "$ORUN"; } || true
else
  echo "(no reports_auto/oneclick/*)"
fi

echo
echo "=== API ==="
if [ -n "$LAST_API" ]; then
  ARUN="$LAST_API/run.log"; AERR="$LAST_API/api.err"; APY="$LAST_API/py_last_trace.txt"; ASRV="$LAST_API/server.log"
  for f in "$ARUN" "$AERR" "$APY" "$ASRV"; do
    [ -f "$f" ] && { echo "[$(basename "$f")] $f (tail-120)"; tail -n 120 "$f"; echo; } || true
  done
  echo "[*] Smoke /classify route=rule"
  curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' \
       -d '{"texts":["想詢問報價與交期","需要技術支援"],"route":"rule"}' | tee "$LAST_API/sanity_smoke_rule.json"
  echo
  echo "[*] Smoke /classify route=ml"
  curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' \
       -d '{"texts":["想詢問報價與交期","需要技術支援"],"route":"ml"}' | tee "$LAST_API/sanity_smoke_ml.json"
  echo
  echo "[*] /tri-eval quick"
  curl -sS -X POST "http://127.0.0.1:${PORT}/tri-eval" -H 'Content-Type: application/json' \
       -d '{"texts":["想詢問報價與交期","需要技術支援","發票抬頭更新"],"labels":["biz_quote","tech_support","profile_update"]}' \
       | tee "$LAST_API/sanity_tri_eval.json"
  echo
else
  echo "(no reports_auto/api/*)"
fi

echo
echo "=== EVAL ==="
if [ -n "$LAST_EVAL" ]; then
  ERUN="$LAST_EVAL/run.log"; EERR="$LAST_EVAL/tri_eval.err"; EPY="$LAST_EVAL/py_last_trace.txt"; ERES="$LAST_EVAL/tri_results.json"
  for f in "$ERUN" "$EERR" "$EPY" "$ERES"; do
    [ -f "$f" ] && { echo "[$(basename "$f")] $f (tail-200 or cat)"; case "$f" in *.json) sed -n '1,200p' "$f";; *) tail -n 200 "$f";; esac; echo; } || true
  done
else
  echo "(no reports_auto/eval/*)"
fi

# Windows 檔案總管快速開啟
if command -v explorer.exe >/dev/null 2>&1; then
  for d in "$LAST_ONECLICK" "$LAST_API" "$LAST_EVAL"; do
    [ -n "$d" ] && [ -d "$d" ] && explorer.exe "$(wslpath -w "$(cd "$d"&&pwd)")" >/dev/null 2>&1 || true
  done
fi
