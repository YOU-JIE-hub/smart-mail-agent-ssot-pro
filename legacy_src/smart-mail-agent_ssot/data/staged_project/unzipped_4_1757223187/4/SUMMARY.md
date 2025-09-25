# 三模型評測摘要

## 資產路徑
- INTENT 權重：`artifacts/intent_pro_cal.pkl`
- INTENT 標準化權重：`artifacts/intent_pro_cal_fixed.pkl`（若 OVERWRITE=1 則原檔已被覆蓋）
- SPAM 權重：`artifacts_prod/model_pipeline.pkl`
- KIE 權重資料夾：`artifacts/releases/kie_xlmr/current/`

## KIE 指標（strict-span）
```
pred_rows=240
gold_rows=240
aligned_rows=240
miss_from_pred=0  # gold多出、pred缺少的出現次數
miss_from_gold=0  # pred多出、gold缺少的出現次數
strict_span_P=0.8629
strict_span_R=0.4084
strict_span_F1=0.5544
```
