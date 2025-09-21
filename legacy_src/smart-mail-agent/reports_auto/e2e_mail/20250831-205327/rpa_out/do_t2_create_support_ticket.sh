#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "t2",
  "action": "create_support_ticket",
  "priority": "P2",
  "queue": "Support",
  "due_at": "2025-08-31T20:53:40+00:00",
  "fields": {
    "sla": "SLA"
  },
  "audit": {
    "source": "sma_actions_exec",
    "model_versions": {
      "spam": "prod",
      "intent": "pro_cal",
      "kie": "xlmr"
    },
    "risk": "medium",
    "created_at": "2025-08-31T12:53:40+00:00"
  },
  "idempotency_key": "e8999c84740444e0168cc7e9d3d9e6ef1f8a5d13"
}
JSON
echo '[RUN]' create_support_ticket t2 priority=P2 queue=Support due_at=2025-08-31T20:53:40+00:00
