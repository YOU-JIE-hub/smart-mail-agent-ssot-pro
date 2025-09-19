#!/usr/bin/env bash
set -Eeuo pipefail
bash scripts/api_up_env.sh start
sleep 1
bash scripts/sanity_all.sh
