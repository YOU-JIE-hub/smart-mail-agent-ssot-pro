# ONE-CLICK Scorecard (20250907T205040)

彙整 Intent / KIE / Spam 的關鍵指標與就緒判定。

## Intent (rules v11c)
- report: `reports_auto/eval/20250907T205034/metrics_intent_rules_hotfix_v11c.md`
- micro P/R/F1: **0.733/0.733/0.733**
- macro F1: **0.670**
- verdict: **PASS**

## KIE (hybrid v4)
- report: `reports_auto/kie_eval/20250907T205036/metrics_kie_spans.md`
- strict micro P/R/F1: **0.907/0.716/0.800**
- strict macro F1: **0.667**
- lenient micro P/R/F1: **0.950/0.750/0.838**
- verdict: **PASS+HIL(SLA)**（SLA 欄位維持 HIL）

## Spam (auto-cal v4)
- report: `reports_auto/eval/20250907T205039/metrics_spam_autocal_v4.md`
- ROC-AUC: **0.992**
- PR-AUC: **0.981**
- Best threshold by F1: **0.405** ，F1=**0.948**
- verdict: **PASS**

