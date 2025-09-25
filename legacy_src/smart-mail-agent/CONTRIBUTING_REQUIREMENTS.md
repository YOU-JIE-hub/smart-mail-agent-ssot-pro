# CONTRIBUTING_REQUIREMENTS

本文件描述本專案「Smart Mail Agent」之工程要求與驗收門檻，對應面試展示所需的一鍵 E2E、可回溯審計與 CI 綠燈。所有變更需遵守本文之命名與路徑，不得任意搬動或改名既有檔案與模型。

---

## 一、總原則

* 一鍵跑全流程：讀 .eml → Spam → Intent → KIE → 決策 → RPA 產物/寄信/票單/差異 → DB/審計。
* 永遠先進專案根目錄並啟動虛擬環境；所有腳本要自動 `source .sma_tools/env_guard.sh`，並固定：
  * `export PYTHONNOUSERSITE=1`
  * `export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"`
* 優先沿用已存在的檔案與路徑；「若缺再補」，禁止大搬家／亂改命名，避免路徑衝突。
* 腳本必須自檢與明確報錯：缺檔/錯版/模型不在位，要清楚印出「缺什麼、去哪找」。
* 不要猜：遇到不確定資料時，腳本要印出現況與預設值，並把產生的檔案路徑回報（可讀可查）。
* 輸出要有審計與可回溯：DB（SQLite）＋ NDJSON pipeline log。
* 面試可演示：要有 `reports_auto/e2e_mail/<ts>/` 目錄，一眼看完 SUMMARY、actions、RPA 產物。
* CI 綠燈：現有單測全部通過；（可選）coverage 高（>95%）但以「所有測試綠燈」為主。

---

## 二、模型相關（必須這樣用）

### Spam（sklearn ensemble）
* 模型與門檻固定讀：
  * `artifacts_prod/model_pipeline.pkl`
  * `artifacts_prod/ens_thresholds.json`
* 提供快速評測腳本 `scripts/sma_quick_eval.py`（已修 f-string / dataset 清理）；輸出報表到 `reports_auto/prod_quick_report.md`。
* 任何新腳本都不得改動這兩個檔名或其相對路徑。

### Intent（多類＋門檻路由）
* 權重與門檻固定讀：
  * `artifacts/intent_pro_cal.pkl`
  * `reports_auto/intent_thresholds.json`
* 反序列化需有 shim（`rules_feat`/`ZeroPad`/`DictFeaturizer` 等缺符號時能載入）。
* 路由讀取預測檔鍵名要保守：`final > pred > label > top`；並處理 `p1/score/gap` 兼容。
* 訓練/門檻調參（如需）：沿用 `reports_auto/intent/.sma_tools/*.py`，不另起爐灶。

### KIE（HF Token Classification）
* 模型目錄自動偵測：優先 `kie/`，次選 `reports_auto/kie/kie/`；不可重命名。
* `id2label` 讀取需健壯：支援 list / dict(key 為 str 或 int) / fallback `label2id`；保證不因 key 型別報錯。
* 輸出 spans 統一格式：`[{"label": "...", "start": int, "end": int}]`。

---

## 三、資料與產物（固定形制）

* Demo `.eml` 放 `data/demo_eml/`，涵蓋 spam/業務/支援/投訴/規則/資料異動。
* 每次 E2E 產出 `reports_auto/e2e_mail/<ts>/`，至少包含：
  * `cases.jsonl`、`actions.jsonl`、`SUMMARY.md`
  * `rpa_out/`：
    * `do_*.sh`（含 idempotency key）
    * `email_outbox/`（file-transport 模擬寄信）
    * `tickets/`、`diffs/`、`faq_replies/`、`quotes/`
* DB 與 Log：
  * SQLite：`db/sma.sqlite`，錯誤表名固定 `err_log(ts, mail_id, stage, message, traceback)`（禁用保留字 `when`）。
  * Pipeline NDJSON：`reports_auto/logs/pipeline.ndjson` 以 append 模式紀錄。

---

## 四、決策與後續行為（固定對映）

* Spam：`ENS=1 ⇒ action=quarantine`（P1 / Security）；否則進入 Intent。
* Intent → Action：
  * `biz_quote` → `create_quote_ticket`（KIE `amount/date_time` 可用則帶入）＋回信模板
  * `tech_support` → `create_support_ticket`（KIE `env/sla` 可用則帶入）＋回信模板
  * `complaint` → `escalate_to_CX`
  * `policy_qa` → `send_policy_docs`
  * `profile_update` → `update_profile`（輸出 JSON diff、標記需審批）
  * 其他 → `manual_triage`
* 佇列與優先級（可調但輸出需穩定）：
  * quarantine→`P1/Security`；support→`P2/Support`；complaint→`P2/Support`；quote→`P1/Sales`；policy→`P3/Compliance`；profile→`P3/CRM`；manual→`P3/Ops`
* 所有行為須在 `actions_plan.ndjson` 有簽章與 `idempotency_key`；`do_*.sh` 引用該 key。

---

## 五、腳本與模組邊界

* 不得移動/改名既有核心腳本與模型檔；新增檔案採「補洞」原則，放在：
  * `scripts/`（管線與行為執行器）
  * `.sma_tools/`（環境守門員／CI 輔助）
  * `ai_rpa/`（單測需要的小模組：`actions.write_json`、`intent_map.to_categories`、`mailguard.detect`、`nlp.analyze_text`、`utils.json_safe.jsonable`）
  * `smart_mail_agent/utils.py`（`logger()`）
* 新檔案必須與現有測試預期相容（函式名、參數名、回傳鍵名）。

---

## 六、CI 與測試

* `pytest -q` 全部通過（以綠燈為主）。
* linters（`ruff`、`isort`）可選：不強改既有風格。
* 新增最小 E2E 煙霧測試：不需大模型，只驗 IO 與 JSON schema。
* 如測試引用舊模組名，提供最小 shim（例如 `ai_rpa.nlp_llm`）且不破壞現行行為。

---

## 七、運維與演示

* 一鍵入口：`./scripts/sma_e2e_mail.sh <eml_dir>`。
* 任何腳本失敗即非 0，並把錯誤同步寫 `err_log` 與 `pipeline.ndjson`。
* 寄信預設 file-transport；如需 SMTP，使用環境變數 `SMTP_*`，不得硬編。
* 大檔（`*.safetensors`、`*.pkl`）由 `.gitattributes`（LFS）或 `.gitignore` 管理，不亂推。
* README/REPORT 必有「三行就跑」：進環境 → 生成 demo → 一鍵 E2E。

---

## 八、固定標籤與對映

* Intent 六類：`biz_quote / tech_support / complaint / policy_qa / profile_update / other`
  * 舊詞如 `sales/quote/rfq/refund` 需在 `ai_rpa.intent_map.to_categories` 正規化到新類。
* KIE 標籤：`date_time / amount / env / sla`
* RPA Action：`quarantine / create_support_ticket / create_quote_ticket / escalate_to_CX / send_policy_docs / update_profile / manual_triage`

---

## 九、可驗收清單（交付即打勾）

* [ ] `./scripts/sma_e2e_mail.sh data/demo_eml` 退出碼 0，並生成 `reports_auto/e2e_mail/<ts>/...`
* [ ] `SUMMARY.md` 出現 Spam/Intent/Actions 統計；`rpa_out/` 含 `do_*.sh`、`email_outbox/`、`tickets/`、`diffs/`、`faq_replies/`、`quotes/`
* [ ] `db/sma.sqlite` 存在且有表：`actions / intent_preds / kie_spans / err_log`
* [ ] `reports_auto/logs/pipeline.ndjson` 有新增流水
* [ ] `pytest -q` 全綠
* [ ] Spam/Intent/KIE 僅從既定路徑讀取，檔名未改動
* [ ] 任一缺檔情況能清楚印出缺什麼與建議處置
