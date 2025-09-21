# CRON Examples

每 15 分（離線最小）：
*/15 * * * * cd ~/projects/smart-mail-agent && ~/.venv/sma/bin/ai-rpa --tasks nlp,actions --output share/smoke_output/cron_report.json >> logs/ai_rpa.log 2>&1
