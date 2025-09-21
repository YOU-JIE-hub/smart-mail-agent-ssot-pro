# .sma_tools 相容層（shim）
本資料夾僅為相容既有腳本（如 scripts/sma_e2e_mail.sh）中 `source .sma_tools/env_guard.sh` 的需求。
功能：提供最小的環境守門與常見函式（assert_root / venv_on / info / warn / require_* 等）。
日後若全面改寫腳本內嵌守門後，方可再移除此相容層。
