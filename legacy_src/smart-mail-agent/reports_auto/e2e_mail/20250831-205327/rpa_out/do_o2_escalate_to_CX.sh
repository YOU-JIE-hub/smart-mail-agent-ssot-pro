#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "o2",
  "action": "escalate_to_CX",
  "priority": "P2",
  "queue": "Support",
  "due_at": "2025-09-01T12:53:40+00:00",
  "fields": {},
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
  "idempotency_key": "20a9d2a8fb28f272a15e46d3c7d010be5172e1c7"
}
JSON
echo '[RUN]' escalate_to_CX o2 priority=P2 queue=Support due_at=2025-09-01T12:53:40+00:00
