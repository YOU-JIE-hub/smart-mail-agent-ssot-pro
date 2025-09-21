#!/usr/bin/env bash
set -Eeuo pipefail

# ---- 解析 ROOT（支援 UNC/相對路徑）----
INPUT_ROOT="${1:-.}"
to_linux() {
  case "$1" in
    \\\\wsl.localhost\\*) s="${1#\\\\wsl.localhost\\}"; s="${s#*\\}"; printf '/%s\n' "${s//\\//}";;
    *) printf '%s\n' "$1";;
  esac
}
ROOT="$(to_linux "$INPUT_ROOT")"
if [ ! -d "$ROOT" ]; then
  echo "[WARN] ROOT not found: $ROOT"
  ROOT="/home/youjie/projects/smart-mail-agent_ssot"
fi
# 不像專案根就回退到預設
if [ ! -d "$ROOT/src/smart_mail_agent" ] && [ -d "/home/youjie/projects/smart-mail-agent_ssot/src/smart_mail_agent" ]; then
  echo "[WARN] '$ROOT' 不是專案根，改用預設專案根"
  ROOT="/home/youjie/projects/smart-mail-agent_ssot"
fi

cd "$ROOT"
echo "[info] PROJECT_ROOT=$(pwd)"

# ---- venv 檢查／啟用 ----
if [ ! -x .venv_clean/bin/python ]; then
  echo "[info] create venv: .venv_clean"
  python3 -m venv .venv_clean
fi
. .venv_clean/bin/activate

# ---- 設 PYTHONPATH ----
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

# ---- 環境摘要 ----
echo "[env]"
python - <<'PY'
import sys, platform, os, pathlib
print(sys.version)
print(platform.platform())
print("PYTHONPATH=", os.environ.get("PYTHONPATH",""))
print("smart_mail_agent exists:", pathlib.Path("src/smart_mail_agent").exists())
PY

# ---- Crash 指針 ----
echo "[last crash pointer]"
if [ -f reports_auto/logs/LAST_CRASH_PATH.txt ]; then
  cat reports_auto/logs/LAST_CRASH_PATH.txt
else
  echo NONE
fi

# ---- Doctor（若缺則提示套 hotfix2）----
if python -c "import smart_mail_agent.cli.doctor" >/dev/null 2>&1; then
  echo "[doctor]"
  python -m smart_mail_agent.cli.doctor
else
  echo "[doctor] 模組缺少，跳過（如需完整診斷：bash sma_enterprise_hotfix2.sh）"
fi

# ---- 重點日誌 ----
echo "[last 120 lines of ALLIN*]"
tail -n 120 reports_auto/oneclick/LATEST/logs/ALLIN_*.log 2>/dev/null || true

echo "[last 80 lines of pipe items]"
tail -n 80 reports_auto/logs/pipe_items.jsonl 2>/dev/null || true

echo "[OK] triage done."
