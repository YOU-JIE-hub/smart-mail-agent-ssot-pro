#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-$(grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || echo 8000)}"
T1='您好，想詢問報價與交期，數量100台'
T2='附件服務無法連線，請協助處理，連絡 0912-345-678'
C=$(curl -sS -X POST "http://127.0.0.1:${PORT}/classify" -H 'Content-Type: application/json' -d "{\"texts\":[\"$T1\",\"$T2\"],\"route\":\"ml\"}")
echo "$C" | jq . || echo "$C"
I1=$(echo "$C" | jq -r '.pred[0]') ; I2=$(echo "$C" | jq -r '.pred[1]')
E=$(curl -sS -X POST "http://127.0.0.1:${PORT}/extract" -H 'Content-Type: application/json' -d "{\"texts\":[\"$T1\",\"$T2\"]}")
echo "$E" | jq . || echo "$E"
P=$(curl -sS -X POST "http://127.0.0.1:${PORT}/plan" -H 'Content-Type: application/json' -d "{\"intents\":[\"$I1\",\"$I2\"]}")
echo "$P" | jq . || echo "$P"
A1=$(echo "$P" | jq -r '.actions[0]') ; A2=$(echo "$P" | jq -r '.actions[1]')
A=$(curl -sS -X POST "http://127.0.0.1:${PORT}/act" -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"mail_id\":\"m1\",\"action\":\"$A1\",\"fields\":$(echo "$E" | jq '.fields[0]')},{\"mail_id\":\"m2\",\"action\":\"$A2\",\"fields\":$(echo "$E" | jq '.fields[1]')}]} ")
echo "$A" | jq . || echo "$A"
ls -1 "$(pwd)/rpa_out" 2>/dev/null | sed "s#^#  rpa_out/#" || true
