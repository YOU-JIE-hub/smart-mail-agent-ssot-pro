import os, json, re, argparse, yaml
from pathlib import Path
HERE = Path(__file__).parent; ROOT = HERE.parent

def read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines()]

def join_subject_text(r):
    if r.get("text"): return r["text"]
    return "  ".join([r.get("subject",""), r.get("body",""), r.get("content","")]).strip()

def detect_lang(text:str):
    return "zh" if re.search(r'[\u4e00-\u9fff]', text) else "en"

def find_spans(patterns, text, label):
    spans=[]
    for p in (patterns or []):
        for m in re.finditer(p["regex"], text, flags=re.I):
            s,e=m.span(0); spans.append({"label":label, "start":s, "end":e, "raw":text[s:e], **{k:v for k,v in p.items() if k!="regex"}})
    return spans

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True)
    ap.add_argument("--rules", default=str(HERE/"ruleset.yml"))
    ap.add_argument("--out_jsonl", default=str(ROOT/"data/kie/silver.jsonl"))
    args=ap.parse_args()

    data=read_jsonl(args.in_jsonl)
    rules=yaml.safe_load(Path(args.rules).read_text(encoding="utf-8"))

    out=[]
    for r in data:
        txt=join_subject_text(r)
        if not txt: continue
        labels=[]
        for field,cfg in rules.items():
            if field in ("version","currency_alias"): continue
            labels.extend(find_spans((cfg or {}).get("patterns"), txt, field))
        out.append({"id": r.get("id") or r.get("mid"), "lang": r.get("lang") or detect_lang(txt), "text": txt, "labels": labels})

    Path(args.out_jsonl).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_jsonl, "w", encoding="utf-8") as f:
        for it in out: f.write(json.dumps(it, ensure_ascii=False)+"\n")
    print(f"[SILVER] {len(out)} -> {args.out_jsonl}")

if __name__=="__main__":
    main()
