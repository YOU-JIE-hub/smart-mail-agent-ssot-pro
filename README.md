# Smart Mail Agent (SSOT Pro)

> 自動化 RPA：收信 → SPAM/INTENT → KIE → 6 大動作（報價、建單、升級建議、FAQ 草稿、CRM 更新、人工轉派）。
> 一鍵產物：reports_auto/actions/latest/** 與 bundles/**

## 快速開始
```bash
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt || true
bash tools/actions_batch6.sh
sed -n '1,80p' reports_auto/actions/latest/actions_summary.md
