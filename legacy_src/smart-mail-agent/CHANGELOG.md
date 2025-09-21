
## Legacy isolation & coverage scope (auto)
- 將歷史模組移至 `archive/legacy_modules/`（保留 `modules/quotation.py` 過渡）
- 新增 `tools/ci-guard.sh` 禁止新代碼引用 `modules.*`（過渡例外：`modules.quotation`）
- 覆蓋率只統計 `src/` 與 `smart_mail_agent/`，排除 `modules/`、`archive/legacy_modules/` 與測試/工具
