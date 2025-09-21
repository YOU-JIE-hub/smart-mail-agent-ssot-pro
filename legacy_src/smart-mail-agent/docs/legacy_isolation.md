# Legacy 模組隔離策略

- 目標：避免歷史檔拉低覆蓋率與干擾開發心智。
- 覆蓋率僅統計：`src/`、`smart_mail_agent/`
- 已封存：`archive/legacy_modules/`（不納入覆蓋率、不再維護）
- 過渡例外：`modules/quotation.py`（等移除依賴後刪除）

## 開發者守則
- 不得在新代碼中引用 `modules.*`（過渡例外：`modules.quotation`）
- CI 可執行 `tools/ci-guard.sh` 作靜態檢查
- 本地回歸：`tools/dev-check.sh g3 && tools/dev-check.sh cov`
