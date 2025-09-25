# Legacy 封存索引
- scripts/e2e_mail_runner.py → 以 `src/smart_mail_agent/cli/e2e.py` 取代（scripts/sma_e2e_mail.sh 僅轉呼叫 CLI）
- 舊 DB（data/stats.db、db/records.db、reports_auto/audit.sqlite3）→ 已合併到 `db/sma.sqlite`
- 一次性工具與快照 → 僅供參考，不再被預設路徑呼叫
