# RAG QA

**問題**：付款條件、交期與付款方式？

**回答**：

（離線）依檢索片段整理：
- 重點1…
- 重點2…

建議：請參照來源片段列表。

---
**來源片段**：

- `/home/youjie/projects/smart-mail-agent_ssot/reports_auto/kb/src/.github__workflows__ci.yml` | env:           OFFLINE: "1"           SMA_ROOT: ${{ github.workspace }}         run: python -m pytest -q -rA       - name: E2E safe (no external I/O)         env:           OFFLINE: "1"           SMA_ROOT: ${{ github.wor
- `/home/youjie/projects/smart-mail-agent_ssot/reports_auto/kb/src/artifacts_inbox__kie_min_bundle__kie__tokenizer_config.json` | {   "added_tokens_decoder": {     "0": {       "content": "&lt;s&gt;",       "lstrip": false,       "normalized": false,       "rstrip": false,       "single_word": false,       "special": true     },     "1": {       "content
- `/home/youjie/projects/smart-mail-agent_ssot/reports_auto/kb/src/kie__tokenizer_config.json` | {   "added_tokens_decoder": {     "0": {       "content": "&lt;s&gt;",       "lstrip": false,       "normalized": false,       "rstrip": false,       "single_word": false,       "special": true     },     "1": {       "content
- `/home/youjie/projects/smart-mail-agent_ssot/reports_auto/kb/src/samples__inbox__mail_09.txt` | 恭喜中獎！USDT 投資回饋計畫，立即買入。
