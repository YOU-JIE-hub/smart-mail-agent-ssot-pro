from __future__ import annotations
import argparse, json, pathlib
from typing import List, Dict, Any, Tuple
from tools.config import get_model_paths
from tools.pipeline_baseline import load_model

def read_jsonl(p: pathlib.Path) -> list[dict]:
    out=[]
    if not p.exists(): return out
    with p.open("r", encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default=None)
    ap.add_argument("--data", default="data/kie_eval/dataset.cleaned.jsonl")
    ap.add_argument("--out",  default="reports_auto/kie/metrics.json")
    args = ap.parse_args()

    paths = get_model_paths(args.cfg)
    model_dir, meta = load_model(paths.kie_dir, "kie")
    outp = pathlib.Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)

    if meta.get("status") not in ("ok","incomplete"):
        with open(args.out, "w", encoding="utf-8") as f: json.dump({"kie": meta}, f, ensure_ascii=False, indent=2)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return

    # 這裡先做「可用性檢查」；真正欄位級 F1 需配合你的任務定義
    data = read_jsonl(pathlib.Path(args.data))
    n = len(data)
    out = {"kie": {"status": meta.get("status"), "ready_flags": meta.get("ready_flags"), "n": n, "model_dir": model_dir}}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__=="__main__":
    main()
