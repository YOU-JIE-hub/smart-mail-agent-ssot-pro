#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"
export OFFLINE="${OFFLINE:-1}"

RED=$'\033[31m'; GRN=$'\033[32m'; BLU=$'\033[34m'; CLR=$'\033[0m'
msg(){ echo "${BLU}[*]${CLR} $*"; }
ok(){  echo "${GRN}[OK]${CLR} $*"; }

clean(){ find "$PROJECT_ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true; }

list_modules(){
  msg "列出 tests* 內引用到的專案模組（去重）"
  grep -RhoE '(from|import) (smart_mail_agent\.[A-Za-z0-9_\.]+|modules\.quotation|ai_rpa\.[A-Za-z0-9_\.]+)' \
    "$PROJECT_ROOT/tests" "$PROJECT_ROOT/legacy_tests" "$PROJECT_ROOT/tests_smoke" 2>/dev/null \
  | sed -E 's/^(from|import) //; s/ .*//' | sort -u
}

case "${1:-}" in
  g3)
    clean
    msg "pytest -q (分組：AI RPA 主流程)"
    pytest -q legacy_tests/ai_rpa/test_cli_actions.py \
             legacy_tests/ai_rpa/test_main_all_success.py \
             legacy_tests/ai_rpa/test_main_actions_dryrun.py \
             legacy_tests/ai_rpa/test_main_error_paths.py \
             legacy_tests/ai_rpa/test_main_nlp_only_no_texts.py
    ok "分組回歸完成"
    ;;
  cov)
    clean
    msg "執行覆蓋率（僅計 src/ai_rpa）"
    pytest -q
    ;;
  golden)
    msg "只跑規則金樣，不帶 coverage"
    pytest -q tests/ai_rpa_unit/test_nlp_rules_golden.py --no-cov
    ;;
  quick)
    msg "只跑 ai_rpa_unit 下的白箱/合約測試，不帶 coverage"
    pytest -q tests/ai_rpa_unit --no-cov
    ;;
  list)
    list_modules
    ;;
  *)
    echo "用法: tools/dev-check.sh {g3|cov|golden|quick|list}"
    exit 2
    ;;
esac
