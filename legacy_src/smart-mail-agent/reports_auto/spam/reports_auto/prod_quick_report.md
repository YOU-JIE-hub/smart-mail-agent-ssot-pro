# Production Quick Report
- Test file: `data/prod_merged/test.jsonl`
- Model: `artifacts_prod/model_pipeline.pkl` 或 `text_lr_platt.pkl`
- Threshold: **0.44**, Signals_min: **3**
- ROC-AUC: **0.9970**, PR-AUC: **0.9970**

## TEXT
- Macro-F1 **0.9788** | Ham P/R/F1 **0.979/0.980/0.979** | Spam P/R/F1 **0.979/0.978/0.978** | CM **[[1541, 32], [33, 1457]]**

## RULE
- Macro-F1 **0.4143** | Ham P/R/F1 **0.531/0.991/0.691** | Spam P/R/F1 **0.888/0.074/0.137** | CM **[[1559, 14], [1379, 111]]**

## ENSEMBLE (部署建議)
- Macro-F1 **0.9748** | Ham P/R/F1 **0.979/0.971/0.975** | Spam P/R/F1 **0.970/0.979/0.974** | CM **[[1528, 45], [32, 1458]]**

附檔：
- False Negatives (漏判 spam)：`reports_auto/prod_errors_fn.tsv`
- False Positives (誤判 ham)：`reports_auto/prod_errors_fp.tsv`
