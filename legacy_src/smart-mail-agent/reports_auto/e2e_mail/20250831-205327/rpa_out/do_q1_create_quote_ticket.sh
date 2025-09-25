#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "q1",
  "action": "create_quote_ticket",
  "priority": "P1",
  "queue": "Sales",
  "due_at": "2025-08-31T20:53:40+00:00",
  "fields": {
    "amount": {
      "raw": "NT"
    },
    "date": {
      "raw": "2025-09-30"
    }
  },
  "audit": {
    "source": "sma_actions_exec",
    "model_versions": {
      "spam": "prod",
      "intent": "pro_cal",
      "kie": "xlmr"
    },
    "risk": "low",
    "created_at": "2025-08-31T12:53:40+00:00"
  },
  "idempotency_key": "c7b1449924df468983227615303d9836d65cb894"
}
JSON
echo '[RUN]' create_quote_ticket q1 priority=P1 queue=Sales due_at=2025-08-31T20:53:40+00:00
