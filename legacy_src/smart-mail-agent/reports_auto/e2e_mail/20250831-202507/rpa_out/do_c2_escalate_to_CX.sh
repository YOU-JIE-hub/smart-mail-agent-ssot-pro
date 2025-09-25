#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "c2",
  "action": "escalate_to_CX",
  "priority": "P2",
  "queue": "Support",
  "due_at": "2025-09-01T12:25:17+00:00",
  "fields": {},
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
  "idempotency_key": "5894daeadf2c4f67d55aff7f8aec81c8248d1f1b"
}
JSON
echo '[RUN]' escalate_to_CX c2 priority=P2 queue=Support due_at=2025-09-01T12:25:17+00:00
