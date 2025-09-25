#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "p2",
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
  "idempotency_key": "5d058ad21fb2572e85e39a5890112d97558662b1"
}
JSON
echo '[RUN]' quarantine p2 priority=P1 queue=Security due_at=2025-08-31T13:53:40+00:00
