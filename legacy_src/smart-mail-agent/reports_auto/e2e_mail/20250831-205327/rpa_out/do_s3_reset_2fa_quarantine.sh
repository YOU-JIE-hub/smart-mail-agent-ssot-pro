#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "s3_reset_2fa",
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
  "idempotency_key": "4ba851ef50b9cdc8b094bc5b5ae8bbb7cc1fd9c7"
}
JSON
echo '[RUN]' quarantine s3_reset_2fa priority=P1 queue=Security due_at=2025-08-31T13:53:40+00:00
