#!/usr/bin/env bash
# oneclick_pro.sh — 固定環境 → API 重啟 → 全套 smoke/tri-eval → 列出絕對路徑
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/oneclick/${TS}"; LOG="$OUT/run.log"; ERR="$OUT/oneclick.err"
mkdir -p "$OUT" reports_auto/.quarantine scripts
exec > >(tee -a "$LOG") 2>&1
on_err(){ c=${1:-$?}; { echo "=== BASH_TRAP(oneclick) ==="; echo "TIME: $(date -Is)"; echo "LAST:${BASH_COMMAND:-<none>}"; echo "CODE:$c"; } >>"$OUT/last_trace.txt"; echo "exit_code=$c" >"$ERR"; echo "[ERR] see: $(cd "$OUT"&&pwd)/oneclick.err"; exit "$c"; }
on_exit(){ ln -sfn "$OUT" reports_auto/LATEST || true; echo "[*] REPORT: $(cd "$OUT"&&pwd)"; command -v explorer.exe >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$(cd "$OUT"&&pwd)")" >/dev/null 2>&1 || true; }
trap 'on_err $?' ERR; trap on_exit EXIT

# 固定資源（你機器上的既定路徑，不猜）
MODEL="/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/artifacts/intent_pro_cal.pkl"
R1="/home/youjie/projects/smart-mail-agent-ssot-pro/intent/intent/.sma_tools/runtime_threshold_router.py"
R2="/home/youjie/projects/smart-mail-agent_ssot/.sma_tools/runtime_threshold_router.py"
[ -f "$MODEL" ] || { echo "[FATAL] 模型不存在: $MODEL"; exit 2; }
RULES="$R1"; [ -f "$RULES" ] || RULES="$R2"; [ -f "$RULES" ] || { echo "[FATAL] 找不到 rules: $R1 或 $R2"; exit 2; }

# venv 復用（兄弟 repo）
[ -e .venv ] || { [ -d /home/youjie/projects/smart-mail-agent_ssot/.venv ] && ln -s /home/youjie/projects/smart-mail-agent_ssot/.venv .venv || true; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true

# env.default（只在不存在時建立；存在則僅校驗模型與規則）
if [ ! -f scripts/env.default ]; then
  cat > scripts/env.default <<ENV
SMA_DRY_RUN=1
SMA_LLM_PROVIDER=none
SMA_EML_DIR=fixtures/eml
SMA_INTENT_ML_PKL=${MODEL}
SMA_RULES_SRC=${RULES}
PORT=8000
ENV
else
  # 修正為你指定的可用路徑（不動其他變數）
  awk -v m="$MODEL" -v r="$RULES" '
    BEGIN{sm=0;sr=0}
    /^SMA_INTENT_ML_PKL=/{print "SMA_INTENT_ML_PKL=" m; sm=1; next}
    /^SMA_RULES_SRC=/{print "SMA_RULES_SRC=" r; sr=1; next}
    {print}
    END{
      if(!sm) print "SMA_INTENT_ML_PKL=" m;
      if(!sr) print "SMA_RULES_SRC=" r;
    }' scripts/env.default > scripts/.env.tmp && mv scripts/.env.tmp scripts/env.default
fi

# 若沒有就補上 api_down / api_where / sanity_all（不覆蓋你現有的）
if [ ! -x scripts/api_down.sh ]; then
  cat > scripts/api_down.sh <<'D'
#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/youjie/projects/smart-mail-agent-ssot-pro
LAST="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
[ -n "$LAST" ] || { echo "[*] no API run dir"; exit 0; }
PIDF="$LAST/api.pid"; [ -f "$PIDF" ] || { echo "[*] no pid file"; exit 0; }
PID="$(cat "$PIDF" 2>/dev/null || true)"; [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
echo "[*] stopped PID=$PID ($PIDF)"
D
  chmod +x scripts/api_down.sh
fi

if [ ! -x scripts/api_where.sh ]; then
  cat > scripts/api_where.sh <<'W'
#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/youjie/projects/smart-mail-agent-ssot-pro
LAST="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
[ -n "$LAST" ] || { echo "[WARN] no API dir"; exit 0; }
echo "RUN_DIR=$(cd "$LAST"&&pwd)"
echo "LOG=$(cd "$LAST"&&pwd)/run.log"
echo "ERR=$(cd "$LAST"&&pwd)/api.err"
echo "PY_LAST=$(cd "$LAST"&&pwd)/py_last_trace.txt"
W
  chmod +x scripts/api_where.sh
fi

if [ ! -x scripts/sanity_all.sh ]; then
  cat > scripts/sanity_all.sh <<'S'
#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-$(grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || echo 8000)}"
API_DIR="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
[ -n "$API_DIR" ] || { echo "[FATAL] no API run dir under reports_auto/api"; exit 2; }
LOG="$API_DIR/run.log"; ERR="$API_DIR/api.err"; PY_LAST="$API_DIR/py_last_trace.txt"; SLOG="$API_DIR/server.log"
jqok(){ command -v jq >/dev/null 2>&1; }
smoke(){ local route="$1"; local out="$API_DIR/sanity_smoke_${route}.json";
  echo "[*] smoke $route -> $out"
  curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' \
    -d '{"texts":["想詢問報價與交期","需要技術支援"],"route":"'"$route"'"}' > "$out" || true
  if jqok; then jq . "$out" || true; else cat "$out" || true; fi
}
tri_eval(){ local out="$API_DIR/sanity_tri_eval.json";
  echo "[*] /tri-eval -> $out"
  curl -sS -X POST "http://127.0.0.1:${PORT}/tri-eval" -H 'Content-Type: application/json' \
    -d '{"texts":["想詢問報價與交期","需要技術支援","發票抬頭更新"],
         "labels":["biz_quote","tech_support","profile_update"]}' > "$out" || true
  if jqok; then jq . "$out" || true; else cat "$out" || true; fi
}
dump(){ echo "[PATHS]"; echo "  RUN_DIR = $(cd "$API_DIR"&&pwd)"; echo "  LOG     = $(cd "$API_DIR"&&pwd)/run.log";
        echo "  ERR     = $(cd "$API_DIR"&&pwd)/api.err"; echo "  PY_LAST = $(cd "$API_DIR"&&pwd)/py_last_trace.txt";
        echo "  SERVER  = $(cd "$API_DIR"&&pwd)/server.log";
        echo "  SMOKE_R = $(cd "$API_DIR"&&pwd)/sanity_smoke_rule.json";
        echo "  SMOKE_M = $(cd "$API_DIR"&&pwd)/sanity_smoke_ml.json";
        echo "  TRI_OUT = $(cd "$API_DIR"&&pwd)/sanity_tri_eval.json"; }
smoke rule || true; smoke ml || true; tri_eval || true; dump
S
  chmod +x scripts/sanity_all.sh
fi

# 起 API（沿用你現有的 api_up.sh；若不在就直接前台跑 http_api_min.py）
if [ -x scripts/api_up.sh ]; then
  scripts/api_down.sh || true
  scripts/api_up.sh
else
  echo "[WARN] scripts/api_up.sh 不在，直接前台起 http_api_min.py"
  set -a; . scripts/env.default 2>/dev/null || true; set +a
  nohup .venv/bin/python scripts/http_api_min.py > "reports_auto/api/${TS}/server.log" 2>&1 &
  echo $! > "reports_auto/api/${TS}/api.pid"
fi

# smoke & tri-eval（API 版）
scripts/sanity_all.sh || true

# 最後再列一次 API 路徑
echo "[*] WHERE API:"
scripts/api_where.sh
