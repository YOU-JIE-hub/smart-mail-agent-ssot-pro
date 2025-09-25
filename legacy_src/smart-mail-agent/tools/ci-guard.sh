#!/usr/bin/env bash
set -Eeuo pipefail
RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; CLR=$'\033[0m'
fail(){ echo "${RED}[GUARD]$CLR $*"; exit 1; }
ok(){ echo "${GRN}[GUARD]$CLR $*"; }

# 拒絕在 src/ 與 tests/ 使用 modules.*（允許 modules.quotation 暫時存在）
if git grep -nE '(^|[^A-Za-z0-9_])from[[:space:]]+modules\.(?!quotation)' -- src tests >/dev/null 2>&1; then
  git grep -nE '(^|[^A-Za-z0-9_])from[[:space:]]+modules\.(?!quotation)' -- src tests
  fail "發現違規 import（from modules.*），請改用 src/ai_rpa 或 smart_mail_agent 等現行模組"
fi
if git grep -nE '(^|[^A-Za-z0-9_])import[[:space:]]+modules\.(?!quotation)' -- src tests >/dev/null 2>&1; then
  git grep -nE '(^|[^A-Za-z0-9_])import[[:space:]]+modules\.(?!quotation)' -- src tests
  fail "發現違規 import（import modules.*），請改用 src/ai_rpa 或 smart_mail_agent 等現行模組"
fi

ok "未發現違規引用 modules.*（保留 modules.quotation 過渡例外）"
