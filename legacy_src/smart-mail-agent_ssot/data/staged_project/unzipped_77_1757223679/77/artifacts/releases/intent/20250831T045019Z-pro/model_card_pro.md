# Intent Classifier (Pro) – Model Card

- Seed: `42`
- Tuned thresholds: `p1=0.52`, `margin=0.15`, `policy_lock=True`
- Test set: `data/intent/external_realistic_test.clean.jsonl` (n=120)

## Metrics
- Before thresholds: **Accuracy 0.8583 / MacroF1 0.8438**
- After thresholds:  **Accuracy 0.9167 / MacroF1 0.9156**  _(ΔAcc +0.0584, ΔMacroF1 +0.0718)_

### Per-class (after thresholds)
- **biz_quote**: P=0.952 / R=1.000 / F1=0.976
- **complaint**: P=0.792 / R=0.950 / F1=0.864
- **other**: P=0.833 / R=0.750 / F1=0.789
- **policy_qa**: P=0.941 / R=0.800 / F1=0.865
- **profile_update**: P=1.000 / R=1.000 / F1=1.000
- **tech_support**: P=1.000 / R=1.000 / F1=1.000

### Top confusions
- other → complaint (3)
- policy_qa → other (2)
- policy_qa → complaint (2)
- other → policy_qa (1)
- other → biz_quote (1)
- complaint → other (1)

## Environment