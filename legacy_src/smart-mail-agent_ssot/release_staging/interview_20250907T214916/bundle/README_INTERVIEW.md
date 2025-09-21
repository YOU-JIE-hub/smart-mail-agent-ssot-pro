# Smart Mail Agent — Interview Bundle
> 把進來的郵件自動「讀懂 → 判斷 → 執行」，把能自動化的工作全做掉，並且可審計、可回放。

## Demo
1) 準備 Python 3.10+、venv；2) 放幾封 .eml 到 demo_eml/；3) `bash scripts/sma_e2e_mail.sh demo_eml`
輸出：reports_auto/e2e_mail/<ts>/（SUMMARY.md、rpa_out/*、db/sma.sqlite、logs/pipeline.ndjson）

## 指標（概要）
- Intent (v11c): micro/macro F1 ≈ 0.733 / 0.670
- KIE (hybrid v4): strict micro F1 ≈ 0.800（SLA 欄位 HIL）
- Spam: ROC-AUC ≈ 0.992，最佳 F1 ≈ 0.948

## 結構
- data_masked/  遮罩資料
- artifacts_prod/ 門檻/校準
- scripts/      一鍵 E2E
- docs/SCORECARD_latest.md  指標
