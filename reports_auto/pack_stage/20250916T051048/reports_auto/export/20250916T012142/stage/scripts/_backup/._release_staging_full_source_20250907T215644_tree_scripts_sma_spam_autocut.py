#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path

def qtile(v, q):
    n = len(v)
    if n == 0: return float("nan")
    if q <= 0: return v[0]
    if q >= 1: return v[-1]
    pos = (n - 1) * q
    i = int(pos); j = min(i + 1, n - 1)
    h = pos - i
    return (1 - h) * v[i] + h * v[j]

root = Path(".")
dd = root / "reports_auto" / "_diag"
cands = sorted(dd.glob("spam_scores_*.ndjson"))
if not cands and (dd / "spam_scores_.ndjson").exists():
    cands = [dd / "spam_scores_.ndjson"]
if not cands:
    print("ERROR: no spam diag NDJSON found under reports_auto/_diag", file=sys.stderr)
    sys.exit(2)

nd = cands[-1]
probs = []
for line in nd.read_text(encoding="utf-8").splitlines():
    if '"prob"' in line:
        try:
            probs.append(float(json.loads(line).get("prob", 0.0)))
        except Exception:
            pass

if not probs:
    print("ERROR: no 'prob' entries in NDJSON", file=sys.stderr); sys.exit(3)

probs.sort()
target = float(os.environ.get("SMA_SPAM_TARGET_RATE", "0.38"))
cut = round(float(qtile(probs, 1 - target)), 4)

th = root / "artifacts_prod" / "ens_thresholds.json"
if not th.exists():
    print(f"ERROR: missing thresholds: {th}", file=sys.stderr); sys.exit(4)

cfg = json.loads(th.read_text(encoding="utf-8"))
cfg["threshold"] = cut
cfg["ens_cut"] = cut
th.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"SMA PRINT OK :: AUTOCUT nd={nd} n={len(probs)} new_cut={cut} target={target}")
