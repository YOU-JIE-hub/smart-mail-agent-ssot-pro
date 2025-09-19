#!/usr/bin/env bash
# 用法：
#   scripts/_crashwrap.sh --cmd 'python -m tools.api_server' [--open]
#   scripts/_crashwrap.sh --cmd 'make up && make smoke'      [--open]
set -Eeuo pipefail -o errtrace

ROOT="${ROOT:-$PWD}"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/ERR/CRASH_${TS}"
mkdir -p "$OUT"
: >"$OUT/run.out"; : >"$OUT/run.err"
SUMMARY="CRASH_SUMMARY.txt"

OPEN="no"
CMD=""

# 讀取 env（若有）
if [ -f scripts/env.default ]; then
  # shellcheck disable=SC1091
  . scripts/env.default || true
fi
export PYTHONNOUSERSITE="${PYTHONNOUSERSITE:-1}"
export PYTHONPATH="${PYTHONPATH:-$ROOT:src:$PYTHONPATH}"
export PYTHONFAULTHANDLER=1   # Python 崩潰時總是寫 traceback

# 參數
while [ $# -gt 0 ]; do
  case "$1" in
    --cmd) shift; CMD="${1:-}";;
    --open) OPEN="yes";;
    --no-open) OPEN="no";;
    *) echo "[WARN] ignore arg: $1";;
  esac
  shift || true
done

if [ -z "${CMD:-}" ]; then
  echo "[FATAL] 必須指定 --cmd '你的指令'" | tee -a "$OUT/run.err"
  exit 2
fi

# 把關鍵環境寫檔（之後檢視）
{
  echo "When   : $TS"
  echo "CWD    : $PWD"
  echo "CMD    : $CMD"
  echo "PYTHON : $(command -v python || true)"
  echo "PYTHONPATH=$PYTHONPATH"
  echo "SMA_RULES_SRC=${SMA_RULES_SRC:-}"
  echo "SMA_INTENT_ML_PKL=${SMA_INTENT_ML_PKL:-}"
} > "$OUT/env.txt"

# EXIT/ERR 收尾：產摘要、打包、嘗試開資料夾
on_finish() {
  ec=$?
  {
    echo "===== CRASH SUMMARY ====="
    echo "When   : $TS"
    echo "CWD    : $PWD"
    echo "Exit   : $ec"
    echo "OutDir : $(readlink -f "$OUT")"
    echo
    echo "----- tail run.err -----"
    tail -n 200 "$OUT/run.err" 2>/dev/null || true
    echo
    echo "----- tail run.out -----"
    tail -n 200 "$OUT/run.out" 2>/dev/null || true
    echo
    # 若你的 API/腳本另有固定錯誤檔，也一併納入
    for f in \
      reports_auto/ERR/api.err \
      reports_auto/ERR/py_last_trace.txt \
      reports_auto/api/manual.err; do
      [ -f "$f" ] || continue
      echo "----- tail $(basename "$f") -----"
      tail -n 200 "$f" || true
      # 複製一份到 OUT 以集中蒐證
      cp -f "$f" "$OUT/$(basename "$f")" 2>/dev/null || true
      echo
    done
  } > "$OUT/$SUMMARY"

  ln -sfn "$OUT" reports_auto/ERR/LATEST_CRASH || true

  # 自動開資料夾（WSL/桌面）
  if [ "$OPEN" = "yes" ]; then
    if command -v explorer.exe >/dev/null 2>&1; then
      explorer.exe "$(wslpath -w "$OUT")" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$OUT" >/dev/null 2>&1 || true
    fi
  fi

  # 給終端一條可視訊息
  echo "[CRASH] 摘要：$OUT/$SUMMARY"
  exit $ec
}
trap on_finish EXIT

# 把所有 stdout/stderr 同步寫到檔案（任何子行程也會跟著）
# 另外用 'script' 做 TTY 錄製，防止行緩衝丟輸出（若有）
exec > >(tee -a "$OUT/run.out") 2> >(tee -a "$OUT/run.err" >&2)

echo "[RUN] $CMD"
if command -v script >/dev/null 2>&1; then
  # 保留一份完整 typescript（最保險）
  script -q -c "bash -lc \"$CMD\"" "$OUT/typescript.txt"
else
  # 無 script 時退化為直接執行（加上 stdbuf 盡量即時）
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL bash -lc "$CMD"
  else
    bash -lc "$CMD"
  fi
fi
