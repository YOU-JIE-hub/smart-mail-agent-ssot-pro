#!/usr/bin/env bash
set -Eeuo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <ssot_bundle_xxx.tgz> [DEST_DIR]"
  exit 1
fi
PKG="$1"; DEST="${2:-$PWD/restored_project}"
mkdir -p "$DEST"
echo "[*] Extract -> $DEST"
tar -xzf "$PKG" -C "$DEST"
cd "$DEST"

# venv
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools >/dev/null

# 安裝 requirements（若有）
if [ -s bundles/requirements.lock ]; then
  echo "[*] pip install -r bundles/requirements.lock (may take a while)"
  python -m pip install -r bundles/requirements.lock || true
fi

# CPU-only deps（避免 CUDA 卡住）
python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.1,<2.6" >/dev/null || true
python -m pip install "transformers>=4.39,<5" "tokenizers>=0.22,<0.23" "safetensors>=0.4,<0.7" >/dev/null || true

# 設 PYTHONPATH
export PYTHONPATH="$PWD:$PWD/src:${PYTHONPATH:-}"

detect_kie() {
  # 優先 KIE_MODEL_DIR（環境或 .env.local），再 bundles/ASSET_HINTS_*，最後回空字串
  if [ -n "${KIE_MODEL_DIR:-}" ] && [ -s "$KIE_MODEL_DIR/config.json" ]; then
    echo "$KIE_MODEL_DIR"; return 0
  fi
  if [ -s .env.local ]; then
    set -a; . ./.env.local; set +a
    if [ -n "${KIE_MODEL_DIR:-}" ] && [ -s "$KIE_MODEL_DIR/config.json" ]; then
      echo "$KIE_MODEL_DIR"; return 0
    fi
  fi
  if ls -1 bundles/ASSET_HINTS_*.json >/dev/null 2>&1; then
    python - <<'PY'
import json, sys
from pathlib import Path
p=sorted(Path("bundles").glob("ASSET_HINTS_*.json"))[-1]
h=json.loads(p.read_text())
cands=[h.get("KIE_MODEL_DIR_env","")] + h.get("KIE_MODEL_DIR_hints",[])
for x in cands:
    if x and (Path(x)/"config.json").exists():
        print(x); sys.exit(0)
print("")
PY
    return 0
  fi
  echo ""
}

KIE="$(detect_kie)"
if [ -z "$KIE" ] && [ "${NONINTERACTIVE:-0}" != "1" ]; then
  echo "[?] KIE model dir not found."
  read -rp "    Enter path to KIE model (folder containing config.json/model.safetensors): " KIE
fi
if [ -n "$KIE" ] && [ -d "$KIE" ] && [ -s "$KIE/config.json" ]; then
  export KIE_MODEL_DIR="$KIE"
  echo "KIE_MODEL_DIR=$KIE_MODEL_DIR" > .env.local
  echo "[*] KIE_MODEL_DIR set to $KIE_MODEL_DIR (also saved in .env.local)"
else
  echo "[!] WARNING: invalid/missing KIE path; KIE steps will fallback to regex-only."
fi

# 驗證：有 tools/run_safe.sh 就跑；否則跑 E2E 安全流程
if [ -x tools/run_safe.sh ]; then
  bash tools/run_safe.sh || true
else
  if [ -f scripts/sma_e2e_all_safe.sh ]; then
    OFFLINE=1 bash scripts/sma_e2e_all_safe.sh || true
  else
    python -m smart_mail_agent.cli.e2e_safe || true
  fi
  echo "[OK] smoke done. See reports_auto/* for outputs."
fi
