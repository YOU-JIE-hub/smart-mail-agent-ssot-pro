# ONECLICK Summary

## Alignment
TOTAL_GOLD=289
MATCHED=282
COVERAGE=0.9758
OUT=reports_auto/alignment/gold2pred_intent.csv

## KIE Summary
[SUMMARY] TOTAL=282 EMPTY=53 | LABEL={'sla': 135, 'date_time': 72, 'amount': 179, 'env': 69} | SOURCE={'kie': 393, 'regex': 62}

## Intent (gold)
```
TASK=intent
GOLD=330 MATCHED=282 COVERAGE=0.8545
ACCURACY=0.0000
F1_macro=0.0000 F1_micro=0.0000 F1_weighted=0.0000
PER_LABEL (label, support, precision, recall, f1)
biz_quote	0	0.0000	0.0000	0.0000
complaint	0	0.0000	0.0000	0.0000
ham	245	0.0000	0.0000	0.0000
other	0	0.0000	0.0000	0.0000
policy_qa	0	0.0000	0.0000	0.0000
profile_update	0	0.0000	0.0000	0.0000
spam	37	0.0000	0.0000	0.0000
tech_support	0	0.0000	0.0000	0.0000```

## Intent (silver/identity)
```
TASK=intent
GOLD=189 MATCHED=189 COVERAGE=1.0000
ACCURACY=1.0000
F1_macro=1.0000 F1_micro=1.0000 F1_weighted=1.0000
PER_LABEL (label, support, precision, recall, f1)
biz_quote	74	1.0000	1.0000	1.0000
complaint	7	1.0000	1.0000	1.0000
policy_qa	38	1.0000	1.0000	1.0000
profile_update	27	1.0000	1.0000	1.0000
tech_support	43	1.0000	1.0000	1.0000```

## Spam (calibrated)
```
TASK=spam threshold=0.05
GOLD=330 MATCHED=282 COVERAGE=0.8545
ACCURACY=0.1312 AUC=0.5
F1_macro=0.2320 F1_micro=0.1312 F1_weighted=0.2320
PER_LABEL (label, support, precision, recall, f1, TP, FP, FN)
0	245	0.0000	0.0000	0.0000	0	245	0
1	37	0.1312	1.0000	0.2320	37	245	0
```

_log: oneclick_all_20250906T151440.log_
