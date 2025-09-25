#!/usr/bin/env python3
import argparse, hashlib, re, sqlite3, sys, os
import json as jsonlib
from pathlib import Path
from collections import Counter, defaultdict

SECTIONS = ["Artifacts & Thresholds", "Action Plan", "Actions Summary", "Downgrade Reasons"]

def sha256_path(p: Path) -> str:
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for ch in iter(lambda: f.read(1<<20), b''): h.update(ch)
    return h.hexdigest()

def drop_sections(md: str, title: str) -> str:
    pat = re.compile(rf"^##\s+{re.escape(title)}\s*$[\s\S]*?(?=^##\s+|\Z)", re.MULTILINE)
    return pat.sub("", md).rstrip() + "\n\n"

def guess_rules_count(obj, depth=0):
    if depth > 8: return 0
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            # list-of-dicts：優先找每項的 rules/patterns/items/data
            sub = 0
            for x in obj:
                for k in ("rules","patterns","items","data"):
                    v = x.get(k) if isinstance(x, dict) else None
                    if isinstance(v, list):
                        sub += len(v)
            return sub or len(obj)
        return len(obj)
    if isinstance(obj, dict):
        for k in ("rules","intents","patterns","items","data"):
            v = obj.get(k)
            if isinstance(v, list) or isinstance(v, dict):
                n = guess_rules_count(v, depth+1)
                if n: return n
    return 0

def read_text_or_json_number(p: Path):
    try:
        o = jsonlib.loads(p.read_text(encoding="utf-8"))
        if isinstance(o, dict):
            for k in ("threshold","thr","ens_threshold","value"):
                if k in o and isinstance(o[k], (int,float)): return float(o[k])
        if isinstance(o, (int,float)): return float(o)
    except Exception:
        pass
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", p.read_text(encoding="utf-8", errors="ignore"))
    return float(m.group(0)) if m else None

def load_actions_plan(plan_path: Path):
    steps_by_type = Counter()
    cases = set()
    hil_cases = set()
    if not plan_path.exists():
        return cases, hil_cases, steps_by_type
    with open(plan_path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln: continue
            try:
                o = jsonlib.loads(ln)
            except Exception:
                continue
            cid = o.get("case_id")
            if cid: cases.add(cid)
            for st in o.get("steps", []) or []:
                t = st.get("type")
                if t: steps_by_type[t] += 1
                if st.get("hil_gate"): 
                    if cid: hil_cases.add(cid)
    return cases, hil_cases, steps_by_type

def load_downgrade_reasons(ndjson_path: Path, run_ts: str):
    counts = Counter()
    if not ndjson_path.exists():
        return counts
    with open(ndjson_path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or '"run_ts":' not in ln: 
                continue
            # 快速過濾
            if run_ts not in ln: 
                continue
            try:
                o = jsonlib.loads(ln)
            except Exception:
                continue
            if o.get("run_ts") != run_ts: 
                continue
            if (o.get("status") or "").lower() != "downgraded":
                continue
            reason = o.get("reason") or o.get("error") or "unspecified"
            counts[str(reason)[:160]] += 1
    return counts

def main(run_dir: str):
    run = Path(run_dir)
    run_ts = run.name
    sm = run/"SUMMARY.md"
    md = sm.read_text(encoding="utf-8") if sm.exists() else f"# E2E Summary ({run_ts})\n"

    # 1) 清理舊段落
    for sec in SECTIONS:
        md = drop_sections(md, sec)

    # 2) Artifacts & Thresholds
    arts = Path("artifacts_prod")
    items = []
    # model pkl
    p = arts/"model_pipeline.pkl"
    if p.exists():
        items.append(f"- model_pipeline.pkl: FOUND (size={p.stat().st_size} bytes, sha256={sha256_path(p)})")
    else:
        items.append("- model_pipeline.pkl: MISSING")
    # ens thresholds
    p = arts/"ens_thresholds.json"
    if p.exists():
        thr = read_text_or_json_number(p)
        items.append(f"- ens_thresholds.json: FOUND ( threshold={thr if thr is not None else 'N/A'})")
    else:
        items.append("- ens_thresholds.json: MISSING")
    # intent rules
    p = arts/"intent_rules_calib_v11c.json"
    if p.exists():
        try:
            obj = jsonlib.loads(p.read_text(encoding="utf-8"))
            rc = guess_rules_count(obj) or 0
        except Exception:
            rc = 0
        items.append(f"- intent_rules_calib_v11c.json: FOUND ( rules={rc})")
    else:
        items.append("- intent_rules_calib_v11c.json: MISSING")
    # kie config
    p = arts/"kie_runtime_config.json"
    if p.exists():
        try:
            obj = jsonlib.loads(p.read_text(encoding="utf-8"))
            eng = obj.get("engine","regex")
        except Exception:
            eng = "regex"
        items.append(f"- kie_runtime_config.json: FOUND ( engine={eng})")
    else:
        items.append("- kie_runtime_config.json: MISSING")

    md += "## Artifacts & Thresholds\n" + "\n".join(items) + "\n\n"

    # 3) Action Plan（由 actions_plan.ndjson）
    cases, hil_cases, steps_by_type = load_actions_plan(run/"actions_plan.ndjson")
    md += "## Action Plan\n"
    md += f"- Cases planned: {len(cases)}\n"
    md += f"- With HIL gate (low confidence): {len(hil_cases)}\n"
    md += "- Steps by type:\n"
    for t,c in sorted(steps_by_type.items()):
        md += f"  - {t}: {c}\n"
    if not steps_by_type:
        md += "  - (none)\n"
    md += "\n"

    # 4) Actions Summary（由 DB 的 actions_compat）
    md += "## Actions Summary\n"
    conn = sqlite3.connect("db/sma.sqlite")
    try:
        # 確認 view 存在
        t = conn.execute("SELECT 1 FROM sqlite_master WHERE type='view' AND name='actions_compat'").fetchone()
        if not t:
            md += f"- No actions view available (actions_compat missing)\n\n"
        else:
            rows = conn.execute("""
              SELECT type, status, COUNT(*) 
              FROM actions_compat 
              WHERE run_ts=? 
              GROUP BY 1,2 
              ORDER BY 1,2;
            """, (run_ts,)).fetchall()
            md += f"- Run: {run_ts}\n"
            md += "- Actions by type/status:\n"
            if rows:
                for t,s,c in rows:
                    md += f"  - {t if t else 'None'}/{s if s else 'None'}: {c}\n"
            else:
                md += "  - (none)\n"
            md += "\n"
    finally:
        conn.close()

    # 5) Downgrade Reasons（從 pipeline.ndjson 匯總）
    dcounts = load_downgrade_reasons(Path("reports_auto/logs/pipeline.ndjson"), run_ts)
    md += "## Downgrade Reasons\n"
    if dcounts:
        for reason, cnt in dcounts.most_common(10):
            md += f"- {reason}: {cnt}\n"
    else:
        md += "- (none)\n"

    sm.write_text(md, encoding="utf-8")
    print(f"[OK] SUMMARY refreshed → {sm}")
    
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    a = ap.parse_args()
    main(a.run_dir)
