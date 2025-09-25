# ONECLICK Summary

## Alignment
TOTAL_GOLD=289
MATCHED=0
COVERAGE=0.0000

## KIE Summary
TOTAL=282 EMPTY=56
LABEL={'sla': 163, 'date_time': 95, 'amount': 148, 'env': 79}
SOURCE={'kie': 393, 'regex': 92}

## Intent (gold)
```
TASK=intent
GOLD=289 MATCHED=282 COVERAGE=0.9758
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
tech_support	0	0.0000	0.0000	0.0000
```

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
tech_support	43	1.0000	1.0000	1.0000
```

## Spam (calibrated, th=0.5)
```
TASK=spam threshold=0.5
GOLD=289 MATCHED=282 COVERAGE=0.9758
ACCURACY=0.8688 AUC=0.5
F1_macro=0.4649 F1_micro=0.8688 F1_weighted=0.8078
PER_LABEL (label, support, precision, recall, f1, TP, FP, FN)
0	245	0.8688	1.0000	0.9298	245	37	0
1	37	0.0000	0.0000	0.0000	0	0	37
```

_log: oneclick_all_20250906T080209.log_
