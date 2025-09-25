# Smart Mail Agent — Architecture

> 此文件對齊目前主程式（`src/ai_rpa/main.py`）行為：任務編排、Spam Gate、Actions 規劃、可選 Playbook 與 Spam 合併。  
> 原則：**不越改越簡略**，新功能採「只加不減／預設關閉」。

## 1. High-level Flow

```mermaid
flowchart TD
    A[Input] -->|--input-path| B[Read text if needed]
    A -->|--tasks| C[Task Plan (normalize)]
    subgraph Spam
      D1[spam_adapter.score]:::opt
      D2[mailguard.detect]:::gate
    end
    classDef gate fill:#ffe8e8,stroke:#d33,stroke-width:1px
    classDef opt fill:#eef7ff,stroke:#36c,stroke-width:1px

    C -->|nlp?| E[nlp.analyze_text]
    C -->|ocr?| F[ocr.run_ocr]
    C -->|scrape?| G[scraper.scrape]
    C -->|classify_files?| H[file_classifier.classify_dir]
    C -->|spam?| D1
    C -->|mailguard?| D2

    E --> I[Action Planner]
    B --> E
    D1 --> J[optional combine]
    D2 --> J[optional combine]
    J --> I

    D2 -->|verdict=BLOCK| X{Gate BLOCK?}
    I -->|if not BLOCK| K[results.actions]

    F --> L[results.ocr]
    G --> M[results.scrape]
    H --> N[results.classify]
    E --> O[results.nlp]
mailguard.detect 為硬性 Gate：BLOCK 時 actions 會 跳過（steps += actions:skipped_by_mailguard）。

spam_adapter.score 與 mailguard.detect 的合併輸出（results.spamcheck_combined）是可選，設 SPAM_COMBINE=1 才會產生；Gate 策略仍以 mailguard 為準。

2. Tasks & Aliases
CLI Task	Exec Name	Result Key	Notes
nlp	nlp	results.nlp	關鍵字/規則（離線）
ocr	ocr	results.ocr	失敗不影響其他
scrape	scrape	results.scrape	需 --allow-online 才建議打外網
classify	classify_files	results.classify	Alias
classify_files	classify_files	results.classify	
spam	spam	results.spam	ML/Adapter
spamcheck	mailguard	results.spamcheck	Alias
mailguard	mailguard	results.spamcheck	Gate

3. Action Planner
基礎：nlp.analyze_text() → intents（如 sales, refund, support）。

規劃路徑（合併去重）：

內建兜底 _plan_actions_from_nlp（關鍵字補洞）

你的 actions.plan_actions(intents)（已保留舊版語意）

Playbook（可選）：ENABLE_PLAYBOOK=1 → 讀 configs/actions_playbook.yaml，以 any/all/none 規則追加動作

mailguard=BLOCK ⇒ 不寫入 results.actions，僅記 steps（安全優先）。

Intent → Action（現行合併矩陣）
Intent/Signal	產生的 Action（去重後）	來源
sales/quote/「合作/報價」	send_quote / route_to_sales	actions.plan_actions / 兜底 / Playbook
support	open_ticket / reply_support	兜底 / actions.plan_actions
refund/「退款/退貨」	initiate_refund	兜底 / Playbook
invoice/「發票」	resend_invoice	Playbook（可選）
cancel_order/「取消訂單」	cancel_order_and_refund	Playbook（可選）
complaint/「抱怨」	escalate_support	Playbook（可選）

4. Spam Multi-layer
Gate：mailguard.detect → ALLOW/REVIEW/BLOCK（BLOCK 直接阻斷 actions）

ML：spam_adapter.score（不阻斷）

合併（可選）：SPAM_COMBINE=1 → results.spamcheck_combined

Verdict 排序：BLOCK > REVIEW > ALLOW

Score 取最大；Reasons 合併去重

5. 運維與驗收（精簡版）
SLO：Pipeline 成功率 ≥ 99%，actions 的誤觸發率 ≤ 1%，mailguard 誤封率 ≤ 0.5%（以人工抽樣驗證）。

DoD：新增規則/動作需附對應測試；--dry-run 無副作用；OFFLINE=1 下無外網請求；steps 必含每一步結果（ok/err/skipped）。

安全：所有對外請求僅在 --allow-online；Secrets 不落地日志；快照已遮罩。

