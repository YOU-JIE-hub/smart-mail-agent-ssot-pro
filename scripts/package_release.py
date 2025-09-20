from __future__ import annotations
import argparse, json, pathlib, hashlib, tarfile, time

def sha256_head(p: pathlib.Path, n=1024*1024) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f: h.update(f.read(n))
    return h.hexdigest()

def add(m: dict, root: pathlib.Path, rel: str):
    p = root / rel
    if p.exists():
        m[rel] = {"size": p.stat().st_size, "sha256_head": sha256_head(p)}
    return m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default="configs/model_paths.yaml")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = pathlib.Path.cwd()
    ts = time.strftime("%Y%m%dT%H%M%S")
    out = args.out or f"release_bundle_{ts}.tar.gz"
    outp = root / out

    manifest = {}
    # 依我們預設 artifacts 路徑收集
    paths = [
        "models/intent/artifacts/v1/intent_pro_cal.pkl",
        "models/intent/artifacts/v1/features.schema.json",
        "models/intent/artifacts/v1/metrics.json",
        "models/intent/artifacts/v1/manifest.json",
        "models/spam/artifacts/v1/spam_rules_lr.pkl",
        "models/spam/artifacts/v1/metrics.json",
        "models/spam/artifacts/v1/manifest.json",
        "models/kie/artifacts/v1/training_report.json",
    ]
    for r in paths:
        add(manifest, root, r)

    (root / "reports_auto" / "summary.json").exists() and add(manifest, root, "reports_auto/summary.json")

    with tarfile.open(outp, "w:gz") as tar:
        for r in manifest.keys():
            tar.add(root / r, arcname=r)
        # 附上 manifest.json
        tmp = root / "reports_auto" / f"MANIFEST_{ts}.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
        tar.add(tmp, arcname="MANIFEST.json")
    print(f"[OK] bundle -> {outp}")

if __name__=="__main__":
    main()
