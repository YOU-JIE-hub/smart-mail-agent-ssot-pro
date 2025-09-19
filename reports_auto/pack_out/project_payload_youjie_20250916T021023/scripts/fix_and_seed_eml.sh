#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"; OUT="reports_auto/seed/${TS}"; LOG="$OUT/run.log"; ERR="$OUT/seed.err"
mkdir -p "$OUT" reports_auto/.quarantine scripts
trap 'echo "exit_code=$?" > "$ERR"; echo "[ERR] see: $(cd "$OUT"&&pwd)/seed.err"; exit 1' ERR
trap 'ln -sfn "$OUT" reports_auto/LATEST || true; echo "[*] REPORT: $(cd "$OUT"&&pwd)"' EXIT
exec > >(tee -a "$LOG") 2>&1
EML_DIR="${SMA_EML_DIR:-}"; if [ -z "$EML_DIR" ]; then
  while IFS= read -r -d '' f; do EML_DIR="$(dirname "$f")"; break; done < <(find . -path './.venv' -prune -o -path './reports_auto' -prune -o -type f -name '*.eml' -print0 | sort -z)
fi
[ -n "$EML_DIR" ] || EML_DIR="fixtures/eml"; mkdir -p "$EML_DIR"
mk(){ f="$1"; [ -f "$f" ] && return 0; cat > "$f" <<'EML'
From: "Acme Sales" <sales@acme.test>
To: youjie@example.com
Subject: 報價與交期詢問
Date: Thu, 11 Sep 2025 10:00:00 +0800
Message-ID: <sample-quote-001@acme.test>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
您好，想詢問產品X的單價與交期，數量100台，請回覆報價單。謝謝。
EML
}
mk "$EML_DIR/sample_1.eml"; mk "$EML_DIR/sample_2.eml"
grep -q '^SMA_EML_DIR=' scripts/env.default 2>/dev/null && sed -i "s|^SMA_EML_DIR=.*|SMA_EML_DIR=${EML_DIR}|" scripts/env.default || echo "SMA_EML_DIR=${EML_DIR}" >> scripts/env.default
N=$(find "$EML_DIR" -type f -name '*.eml' | wc -l | tr -d ' ')
[ "$N" -ge 1 ] || { echo "[FATAL] no .eml"; exit 3; }
printf '{"eml_dir":"%s","count":%d}\n' "$(cd "$EML_DIR"&&pwd)" "$N" > "$OUT/seed_summary.json"
echo "[OK] EML ready ($N files) at $(cd "$EML_DIR"&&pwd)"
