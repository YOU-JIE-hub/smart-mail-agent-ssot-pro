#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "s4_cn_phish",
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
  "idempotency_key": "6beec23d9d8c4629c663a1c36970ec8c7dd7fbdf"
}
JSON
echo '[RUN]' escalate_to_CX s4_cn_phish priority=P2 queue=Support due_at=2025-09-01T12:53:40+00:00
