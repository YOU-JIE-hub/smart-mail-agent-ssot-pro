#!/usr/bin/env bash
set -euo pipefail
latest() { ls -t "$1" 2>/dev/null | head -n1 || true; }
echo "Latest scorecard:    $(latest reports_auto/status/SCORECARD_*.md)"
echo "Latest masked dump:  $(ls -td reports_auto/final_dump/*/ 2>/dev/null | head -n1)"
echo "Latest public pack:  $(latest release_staging/public_bundle_*.tar.gz)"
echo "Latest private pack: $(latest release_staging/private_bundle_*.tar.gz)"
echo "Latest intent rep:   $(latest reports_auto/eval/*/metrics_intent_rules_hotfix_v11*.md)"
echo "Latest kie rep:      $(latest reports_auto/kie_eval/*/metrics_kie_spans.md)"
echo "Latest spam rep:     $(latest reports_auto/eval/*/metrics_spam_autocal_v4.md)"
