import os, json, sys, pathlib, time
root = pathlib.Path(".")
out = root/"reports_auto"; out.mkdir(parents=True, exist_ok=True)
st = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
ok = True
for k, kind in [("INTENT_PKL","file"),("SPAM_PKL","file"),("KIE_DIR","dir")]:
    p = os.environ.get(k,"")
    item = {"env": k, "value": p, "kind": kind, "exists": False}
    if p:
        q = pathlib.Path(p).expanduser().resolve()
        item["resolved"] = str(q)
        item["exists"] = q.exists() and (q.is_file() if kind=="file" else q.is_dir())
    else:
        item["resolved"] = ""
    st[k] = item
    ok = ok and item["exists"]
(out/"validate_env.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(st, ensure_ascii=False, indent=2))
sys.exit(0 if ok else 2)
