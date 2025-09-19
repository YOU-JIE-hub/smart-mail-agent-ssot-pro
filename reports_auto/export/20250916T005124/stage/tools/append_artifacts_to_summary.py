#!/usr/bin/env python3
import json, hashlib, sys
from pathlib import Path

def sha256(p: Path):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for ch in iter(lambda: f.read(1<<20), b''): h.update(ch)
    return h.hexdigest()

def guess_rules_count(obj, depth=0):
    if depth > 3: return 0
    if isinstance(obj, list):
        # 視為規則清單（元素多為 dict）
        if obj and all(isinstance(x, dict) for x in obj): return len(obj)
        return len(obj)
    if isinstance(obj, dict):
        # 常見鍵
        for k in ("rules","intents","patterns","items","data"):
            v = obj.get(k)
            if isinstance(v, list): return guess_rules_count(v, depth+1)
        # 遍歷子鍵
        for v in obj.values():
            if isinstance(v, (list, dict)):
                n = guess_rules_count(v, depth+1)
                if n: return n
    return 0

def main(run_dir:str):
    run = Path(run_dir); sm = run/"SUMMARY.md"
    arts = Path("artifacts_prod")
    items = [
        ("model_pipeline.pkl","PKL"),
        ("ens_thresholds.json","Thresholds"),
        ("intent_rules_calib_v11c.json","IntentRules"),
        ("kie_runtime_config.json","KIEConfig"),
    ]
    lines = ["", "## Artifacts & Thresholds"]
    for fname, _ in items:
        p = arts / fname
        if not p.exists():
            lines.append(f"- {fname}: MISSING"); continue
        if p.suffix == ".pkl":
            lines.append(f"- {fname}: FOUND (size={p.stat().st_size} bytes, sha256={sha256(p)})")
        else:
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
                extra = ""
                if fname == "ens_thresholds.json":
                    if isinstance(obj, dict):
                        thr = obj.get("threshold") or obj.get("spam")
                        if thr is not None: extra = f" threshold={thr}"
                elif fname.startswith("intent_rules"):
                    extra = f" rules={guess_rules_count(obj) or 0}"
                elif fname == "kie_runtime_config.json":
                    eng = (obj.get("engine") or obj.get("mode") or "regex")
                    extra = f" engine={eng}"
                lines.append(f"- {fname}: FOUND{(' ('+extra+')') if extra else ''}")
            except Exception as e:
                lines.append(f"- {fname}: FOUND (unreadable JSON: {e})")
    sm.write_text(sm.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8")
    print("[OK] SUMMARY.md appended (Artifacts & Thresholds) →", sm)

if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv)>1 else None
    if not rd or not Path(rd,"cases.jsonl").exists():
        print("[FATAL] provide run_dir with cases.jsonl", file=sys.stderr); sys.exit(3)
    main(rd)
