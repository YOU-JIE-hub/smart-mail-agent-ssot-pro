#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "c1",
  "action": "quarantine",
  "priority": "P1",
  "queue": "Security",
  "due_at": "2025-08-31T13:25:17+00:00",
  "fields": {},
  "audit": {
    "source": "sma_actions_exec",
    "model_versions": {
      "spam": "prod",
      "intent": "pro_cal",
      "kie": "xlmr"
    },
    "risk": "high",
    "created_at": "2025-08-31T12:25:17+00:00"
  },
  "idempotency_key": "f5e733111733c860495318d63af78a73e4dd5175"
}
JSON
echo '[RUN]' quarantine c1 priority=P1 queue=Security due_at=2025-08-31T13:25:17+00:00
