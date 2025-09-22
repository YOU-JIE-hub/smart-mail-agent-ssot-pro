#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || exit 96
LOG=".sma_logs/kie_env_$(date +%Y-%m-%d_%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY="$(command -v python3 || command -v python)"; fi
echo "[ENV] PY=$PY"
$PY - <<'PY'
import sys,subprocess
need=["sacremoses","sentencepiece","protobuf"]
for p in need:
  try:
    __import__("sacremoses" if p=="sacremoses" else p)
    print(f"[OK] {p} already installed")
  except Exception:
    print(f"[FIX] installing {p} ...", flush=True)
    subprocess.check_call([sys.executable,"-m","pip","install","-q",p])
print("[SANITY] Try AutoTokenizer(xlm-roberta-base)")
from transformers import AutoTokenizer
AutoTokenizer.from_pretrained("xlm-roberta-base")
print("[SANITY] tokenizer ok")
PY
echo "[DONE] env fix"
