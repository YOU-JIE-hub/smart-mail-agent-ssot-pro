# Smart Mail Agent (SSOT Pro)

> 一鍵評測與可視化產物：Pro（校準/ECE/建議閾值）、API Shim（/healthz /readyz /v1/predict/*）、RPA 六動作、審計 SQLite、Bundles。

## Quickstart
```bash
python -m venv .venv && . .venv/bin/activate
pip install -U pip
# 一鍵全跑（Pro→Calib→API→Smoke→E2E→Actions→Audit→Bundles）
bash tools/run_all.sh
# 只做線上 API smoke（臨時啟服務→驗證→關閉）
bash tools/api_smoke.sh
API（shim，若正式服務未提供時兜底）
GET /health / /healthz：200

GET /ready / /readyz：200

POST /v1/predict/spam ：{"text": "..."} → {"prob": 0.xx, "label": "spam|ham"}

POST /v1/predict/intent ：{"text": "..."} → {"label": "...", "score": 0.xx}

POST /v1/predict/kie ：抽取 amounts/phones/emails

產物路徑
Pro：reports_auto/pro/latest/summary.md

Online：reports_auto/online/<TS>/online_smoke.md

E2E：reports_auto/e2e/<TS>/run_summary.md

Actions：reports_auto/actions/latest/*

Bundles：reports_auto/bundles/*.zip

錯誤：reports_auto/ERR/<TS>/*
