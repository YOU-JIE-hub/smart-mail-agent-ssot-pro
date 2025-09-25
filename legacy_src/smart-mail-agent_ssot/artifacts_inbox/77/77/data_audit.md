# Data Audit

## Intent

- Gold: `data/intent/test_labeled.jsonl`  (from `/home/youjie/projects/smart-mail-agent/data/intent/external_realistic_test.clean.jsonl`)

- N: **120**
- Labels: `['biz_quote', 'complaint', 'other', 'policy_qa', 'profile_update', 'tech_support']`


## Spam

- Gold: **MISSING** at `data/spam/test_labeled.jsonl`

- Your previous infer input: `data/intent/external_realistic_test.clean.jsonl` | ids=120
- Intersect ids with gold: **0**
  - ⚠️ ID sets do **NOT** align. This is why eval showed '沒有可對齊的 id'.
- Built aligned infer input: **not available** (couldn't find matching IDs under `data/**`).
