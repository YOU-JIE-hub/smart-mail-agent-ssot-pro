#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "t1",
  "action": "create_support_ticket",
  "priority": "P2",
  "queue": "Support",
  "due_at": "2025-08-31T20:25:17+00:00",
  "fields": {
    "env": "staging"
  },
  "audit": {
    "source": "sma_actions_exec",
    "model_versions": {
      "spam": "prod",
      "intent": "pro_cal",
      "kie": "xlmr"
    },
    "risk": "medium",
    "created_at": "2025-08-31T12:25:17+00:00"
  },
  "idempotency_key": "a3afb4ff7b37cfa9689cb571dc2d235a97bbe50b"
}
JSON
echo '[RUN]' create_support_ticket t1 priority=P2 queue=Support due_at=2025-08-31T20:25:17+00:00
