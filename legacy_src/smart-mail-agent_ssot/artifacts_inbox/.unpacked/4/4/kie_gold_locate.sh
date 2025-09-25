#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(pwd)"
CAND_TEST="data/kie/test.jsonl"
CAND_VALID="data/kie/valid.jsonl"

# 決定當時測試用的標註檔（test.jsonl 優先；沒有就用 valid.jsonl）
GOLD=""
if [[ -f "$CAND_TEST" ]]; then
  GOLD="$CAND_TEST"
  echo "[USE] test gold = $GOLD"
elif [[ -f "$CAND_VALID" ]]; then
  GOLD="$CAND_VALID"
  echo "[USE] fallback gold = $GOLD"
else
  echo "[FATAL] 找不到 data/kie/test.jsonl 或 data/kie/valid.jsonl" >&2
  exit 90
fi

# 統計：樣本數、總 spans、每標籤數量
python - <<'PY' "$GOLD"
import json, sys, collections, pathlib
p = pathlib.Path(sys.argv[1])
n=0; labs=collections.Counter()
with p.open('r',encoding='utf-8',errors='ignore') as f:
    for ln in f:
        if not ln.strip(): continue
        o=json.loads(ln)
        for s in o.get("spans", []):
            labs[s.get("label","<NA>")] += 1
        n += 1
print(f"[STAT] pairs={n} spans_total={sum(labs.values())} per_label={dict(labs)}")
PY

echo "[HEAD] $GOLD (前 3 行)："
sed -n '1,3p' "$GOLD" || true

# 備份到 reports_auto/kie_gold_backup/
STAMP="$(date +%Y%m%d-%H%M%S)"
OUTDIR="reports_auto/kie_gold_backup"
mkdir -p "$OUTDIR"
BASENAME="$(basename "$GOLD")"
BACKUP="$OUTDIR/${STAMP}_${BASENAME}"
cp -f "$GOLD" "$BACKUP"
echo "[BACKUP] -> $BACKUP"

# 附帶列出評測快照（如果有的話）
if [[ -f reports_auto/kie_eval_release_snap.txt ]]; then
  echo "[SNAPSHOT] reports_auto/kie_eval_release_snap.txt (前 6 行):"
  sed -n '1,6p' reports_auto/kie_eval_release_snap.txt || true
else
  echo "[SNAPSHOT] 沒找到 reports_auto/kie_eval_release_snap.txt（可忽略）"
fi
