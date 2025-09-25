# Smart Mail Agent (SSOT Pro)

![api-smoke](https://github.com/YOU-JIE-hub/smart-mail-agent-ssot-pro/actions/workflows/api_smoke.yml/badge.svg)
![nightly](https://github.com/YOU-JIE-hub/smart-mail-agent-ssot-pro/actions/workflows/actions_nightly.yml/badge.svg)
![pro-eval-gate](https://github.com/YOU-JIE-hub/smart-mail-agent-ssot-pro/actions/workflows/pro_eval_gate.yml/badge.svg)

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

## 5 分鐘重現（面試流程）

```bash
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="$PWD:$PWD/src:${PYTHONPATH:-}"

make rag-build
make rag-qa Q="理賠需要哪些文件？"      # 輸出帶 CITATIONS

APP=sma.api.service_compat:app make demo # 產生 RPA 產物（ticket/CRM/FAQ/quote/handoff）
ls -R reports_auto/actions/latest | sed -n '1,160p'

make pro-all && make model-card           # 模型卡 & 指標
sed -n '1,80p' MODEL_CARD.md

make data-audit && sed -n '1,60p' reports_auto/data/profile_latest.md
