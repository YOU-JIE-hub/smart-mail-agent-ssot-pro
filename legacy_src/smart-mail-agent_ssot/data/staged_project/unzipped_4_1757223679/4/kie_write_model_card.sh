#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || exit 96
OUT="reports_auto/model_card_kie.md"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sha() { [ -s "$1" ] && (sha256sum "$1" 2>/dev/null || shasum -a256 "$1") | awk '{print $1}' || echo "NA"; }
lc() { [ -s "$1" ] && wc -l < "$1" || echo 0; }

cat > "$OUT" <<EOF
# KIE Model Card

**Timestamp (UTC)**: $ts

## Data & Rules
- train: \`data/intent/train_aug.jsonl\` (lines=$(lc data/intent/train_aug.jsonl), sha=$(sha data/intent/train_aug.jsonl))
- val:   \`data/intent/val_aug.jsonl\`   (lines=$(lc data/intent/val_aug.jsonl), sha=$(sha data/intent/val_aug.jsonl))
- test:  \`data/intent/test.jsonl\`      (lines=$(lc data/intent/test.jsonl), sha=$(sha data/intent/test.jsonl))
- rules: \`.sma_tools/ruleset.yml\`      (sha=$(sha .sma_tools/ruleset.yml))

## Metrics (strict / partial / field-level / value-equivalence / robustness)
\`\`\`
$(sed -n '1,200p' reports_auto/kie_eval.txt 2>/dev/null || echo "<missing kie_eval.txt>")
$(sed -n '1,120p' reports_auto/kie_field_recall.txt 2>/dev/null || echo "<missing kie_field_recall.txt>")
$(sed -n '1,120p' reports_auto/kie_robust.txt 2>/dev/null || echo "<missing kie_robust.txt>")
\`\`\`

## Training Args (snapshot)
- model: xlm-roberta-base
- epochs: 5, lr=3e-5, max_length=384, batch_size=16, grad_accum=2, seed=42, warmup_ratio=0.1, early_stopping

## Release Gates
- strict F1 ≥ 0.88, partial F1 ≥ 0.93
- per-field F1 (amount/date_time/env/sla) ≥ 0.90
- value equivalence ≥ 0.92
- robustness stability ≥ 0.95
EOF
echo "[OK] -> $OUT"
