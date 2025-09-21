#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# 3.1 先做能自動修的
ruff format src tests || true
ruff check src tests --select I,F401,UP --fix || true
# 再跑一次格式化（常把分號、長行與 import 調整好）
ruff format src tests || true

# 3.2 重新跑 dump
bash scripts/sma_dump_all.sh
