#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "s1_verify_account",
  "action": "quarantine",
  "priority": "P1",
  "queue": "Security",
  "due_at": "2025-08-31T13:53:40+00:00",
  "fields": {},
  "audit": {
    "source": "sma_actions_exec",
    "model_versions": {
      "spam": "prod",
      "intent": "pro_cal",
      "kie": "xlmr"
    },
    "risk": "high",
    "created_at": "2025-08-31T12:53:40+00:00"
  },
  "idempotency_key": "0131ea476ea01708bdf77d9895e2d89845545d26"
}
JSON
echo '[RUN]' quarantine s1_verify_account priority=P1 queue=Security due_at=2025-08-31T13:53:40+00:00
