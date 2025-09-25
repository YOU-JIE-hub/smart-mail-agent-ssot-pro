import json, pathlib, yaml, glob
root=pathlib.Path("."); pro=root/"reports_auto/pro"
def pick_latest():
    p=pro/"latest"/"summary.json"
    if p.exists(): return p
    c=sorted(glob.glob(str(pro/"pro_*/summary.json")))
    return pathlib.Path(c[-1]) if c else None
p=pick_latest(); assert p is not None, "no pro summary"
j=json.loads(p.read_text("utf-8"))
spam_thr = (j.get("spam",{}) or {}).get("recommended_threshold",{}).get("threshold", 0.5)
cfg={"inference":{"spam":{"threshold": float(spam_thr)}}}
out=root/"configs"; out.mkdir(parents=True, exist_ok=True)
(out/"runtime_thresholds.yaml").write_text(yaml.dump(cfg, sort_keys=False, allow_unicode=True), "utf-8")
print("[OK] wrote", out/"runtime_thresholds.yaml")
