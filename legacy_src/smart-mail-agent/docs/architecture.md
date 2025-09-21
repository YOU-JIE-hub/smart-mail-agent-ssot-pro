# Architecture

本專案分層：

- **Ingestion**：`smart_mail_agent/ingestion/*` — 郵件欄位抽取、寫回分類結果等
- **Features (classic)**：`smart_mail_agent/features/*` — 傳統 RPA/規則/記錄器等（多為示範）
- **Spam 模組**：`smart_mail_agent/spam/*` 與 `features/spam/*` — 離線版 orchestrator、規則檢測
- **Routing**：`smart_mail_agent/routing/*` — 行為編排與 CLI 入口（`run_action_handler`）
- **Utils**：`smart_mail_agent/utils/*` — PDF 安全、日誌、設定、驗證器

## CLI

- 幫助：`PYTHONPATH=src python -m src.run_action_handler --help`
- 離線示範：`scripts/demo_offline.sh`

## 測試策略

- CI 僅跑 `tests/unit`、`tests/contracts` 並加 `-m "not online"`，確保離線可重現。
- 覆蓋率徽章：`assets/badges/coverage.svg`（由本地或 CI 更新）。
