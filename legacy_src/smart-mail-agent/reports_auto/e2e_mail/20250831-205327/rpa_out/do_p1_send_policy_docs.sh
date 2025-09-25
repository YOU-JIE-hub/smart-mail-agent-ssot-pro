#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "p1",
  "action": "send_policy_docs",
  "priority": "P3",
  "queue": "Compliance",
  "due_at": "2025-09-02T12:53:40+00:00",
  "fields": {},
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
  "idempotency_key": "c05ae43ae4a449fe9578ef41ede80e7df1b68999"
}
JSON
echo '[RUN]' send_policy_docs p1 priority=P3 queue=Compliance due_at=2025-09-02T12:53:40+00:00
