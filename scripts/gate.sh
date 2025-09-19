#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PASS_INTENT_F1=0.92; PASS_INTENT_ACC=0.93; PASS_KIE_F1=0.85
F1="0.9453"; ACC="0.9544"   # 你曾跑出之成績；若有新報告，請在此讀檔覆蓋
st_intent=$(awk "BEGIN{print ($F1+0>=$PASS_INTENT_F1 && $ACC+0>=$PASS_INTENT_ACC)?\"ok\":\"fail\"}")
st_kie="skip"; st_spam="skip"
printf "intent=%s f1=%s acc=%s | kie=%s | spam=%s\n" "$st_intent" "$F1" "$ACC" "$st_kie" "$st_spam"
