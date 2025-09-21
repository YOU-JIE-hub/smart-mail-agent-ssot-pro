# KIE span metrics (hybrid hotfix v4)
- gold_file: data/kie_eval/gold_merged.jsonl
- pred_files: 94 (hybrid=rules+model)
- total_kept_spans: 420
- strict micro P/R/F1: 0.907/0.716/0.800
- strict macro F1: 0.667

|label|P|R|F1|TP|FP|FN|
|---|---:|---:|---:|---:|---:|---:|
|amount|0.926|0.610|0.735|75|6|48|
|date_time|0.932|0.895|0.913|205|15|24|
|env|0.855|0.790|0.821|94|16|25|
|sla|0.778|0.115|0.200|7|2|54|

## lenient (IoU≥0.50)
- lenient micro P/R/F1: 0.950/0.750/0.838
- lenient macro F1: 0.703
|label|P|R|F1|TP|FP|FN|
|---|---:|---:|---:|---:|---:|---:|
|amount|0.963|0.634|0.765|78|3|45|
|date_time|0.950|0.913|0.931|209|11|20|
|env|0.955|0.882|0.917|105|5|14|
|sla|0.778|0.115|0.200|7|2|54|

## kept spans by source (model / rule / mix)
```json
{
  "model": {
    "amount": 4,
    "date_time": 5,
    "env": 4,
    "sla": 2
  },
  "rule": {
    "amount": 62,
    "date_time": 172,
    "env": 89,
    "sla": 3
  },
  "mix": {
    "amount": 15,
    "date_time": 43,
    "env": 17,
    "sla": 4
  }
}
```

- dumped unmatched examples -> reports_auto/kie_eval/20250907T205036/unmatched_examples.jsonl