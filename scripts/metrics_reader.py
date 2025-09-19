from pathlib import Path
import json
def load_json(p):
    P=Path(p)
    if not P.exists(): return {}
    try: return json.loads(P.read_text("utf-8"))
    except: return {}
def load_artifact_metrics(task_root):
    r=Path(task_root)/"registry.json"
    if not r.exists(): return {}
    active=(json.loads(r.read_text("utf-8")) or {}).get("active")
    d=Path(task_root)/"artifacts"/active
    return {"metrics": load_json(d/"metrics.json"), "thresholds": load_json(d/"thresholds.json"), "version": active}
