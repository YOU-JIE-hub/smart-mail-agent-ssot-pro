#!/usr/bin/env bash
set -euo pipefail
# demo：把 payload 當作入參；未接外部系統前可先 echo / curl 內網 API
cat <<'JSON' > payload.json
{
  "id": "s2_invoice_zip",
  "action": "manual_triage",
  "priority": "P3",
  "queue": "Ops",
  "due_at": "2025-09-03T12:53:40+00:00",
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
  "idempotency_key": "7b3d5117651731680ba797cdbbe8733873220b60"
}
JSON
echo '[RUN]' manual_triage s2_invoice_zip priority=P3 queue=Ops due_at=2025-09-03T12:53:40+00:00
