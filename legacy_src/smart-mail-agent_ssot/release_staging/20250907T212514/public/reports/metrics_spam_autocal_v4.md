# Spam metrics (auto-cal hotfix v4)
- preds: artifacts_prod/text_predictions_test.tsv
- rows: 632
- ROC-AUC: 0.992
- PR-AUC: 0.981

## Best threshold by F1
- threshold: **0.405**
- P/R/F1: **0.944/0.953/0.948**
- TP/FP/FN/TN: 201/12/10/409

## Metrics at current production threshold
- threshold: **0.405**
- P/R/F1: **0.944/0.953/0.948**
- TP/FP/FN/TN: 201/12/10/409

## Suggested production values
```json
{
  "spam": 0.405
}
```