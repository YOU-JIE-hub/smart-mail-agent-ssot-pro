import argparse, json, re, sys
from pathlib import Path
from collections import Counter

ID_PREFIX = "i-20250901-"
ALLOWED_LABELS = ["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]
ALLOWED_PH = {"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

def parse_id(id_str:str)->int:
    if not id_str.startswith(ID_PREFIX): raise ValueError(f"id must start with {ID_PREFIX}: {id_str}")
    seq = id_str[len(ID_PREFIX):]
    if not re.fullmatch(r"\d{4}", seq): raise ValueError(f"id sequence must be 4 digits: {id_str}")
    idx = int(seq)
    if not (1 <= idx <= 120): raise ValueError(f"id out of range: {id_str}")
    return idx

def expect_label_lang(idx:int):
    if   1<=idx<=42:   lab="biz_quote"
    elif 43<=idx<=72:  lab="tech_support"
    elif 73<=idx<=86:  lab="policy_qa"
    elif 87<=idx<=98:  lab="profile_update"
    elif 99<=idx<=110: lab="complaint"
    else:              lab="other"
    if   lab=="biz_quote":     lang = "zh" if idx<=30 else "en"
    elif lab=="tech_support":  lang = "zh" if idx<=63 else "en"
    elif lab=="policy_qa":     lang = "zh" if idx<=82 else "en"
    elif lab=="profile_update":lang = "zh" if idx<=94 else "en"
    elif lab=="complaint":     lang = "zh" if idx<=106 else "en"
    else:                      lang = "zh" if idx<=117 else "en"
    return lab, lang

def has_real_url_or_phone(text:str)->bool:
    if re.search(r"\bhttps?://|\bwww\.", text, re.I): return True
    t = re.sub(r"<PHONE>", "", text)
    if re.search(r"(?:\+?\d[\s\-()]*){7,}", t): return True
    return False

def placeholders_ok(text:str)->bool:
    toks = re.findall(r"<([A-Z_]+)>", text)
    return all(t in ALLOWED_PH for t in toks)

def cleanse_stray_backslashes(line:str)->str:
    return re.sub(r'\\(?!["\\/bfnrtu])', '', line)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", default="data/intent_split")
    ap.add_argument("--fail-on-error", action="store_true")
    args = ap.parse_args()

    src = Path(args.input); outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    raw_lines = [ln.rstrip("\n") for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    fixed_objs, errors, seen = [], [], set()

    for ln_no, line in enumerate(raw_lines, 1):
        fixed_line = cleanse_stray_backslashes(line)
        try:
            obj = json.loads(fixed_line)
        except Exception as e:
            errors.append(f"[JSON] line {ln_no}: {e}")
            continue

        for k in ("id","text","label","meta"):
            if k not in obj:
                errors.append(f"[SCHEMA] line {ln_no}: missing {k}")
                continue

        try:
            idx = parse_id(obj["id"])
        except Exception as e:
            errors.append(f"[ID] line {ln_no}: {e}")
            continue

        if obj["id"] in seen:
            errors.append(f"[ID] line {ln_no}: duplicated {obj['id']}")
        seen.add(obj["id"])

        exp_lab, exp_lang = expect_label_lang(idx)
        if obj["label"] != exp_lab:
            errors.append(f"[LABEL] {obj['id']}: {obj['label']} != {exp_lab}")

        meta = obj["meta"]
        if not isinstance(meta, dict):
            errors.append(f"[META] {obj['id']}: meta must be object")
            continue
        if meta.get("language") != exp_lang:
            errors.append(f"[LANG] {obj['id']}: {meta.get('language')} != {exp_lang}")
        if meta.get("source") != "synthetic":
            errors.append(f"[META] {obj['id']}: source must be 'synthetic'")
        if float(meta.get("confidence", 0)) != 1.0:
            errors.append(f"[META] {obj['id']}: confidence must be 1.0")

        text = obj["text"]
        if not isinstance(text, str) or not text.strip():
            errors.append(f"[TEXT] {obj['id']}: empty text")
            continue

        if has_real_url_or_phone(text):
            errors.append(f"[PII] {obj['id']}: real url/phone")
        if not placeholders_ok(text):
            errors.append(f"[PH] {obj['id']}: non-whitelisted placeholder")

        obj["text"] = text.replace("\r\n","\n").replace("\n","\\n")
        fixed_objs.append(obj)

    if len(fixed_objs)!=120:
        errors.append(f"[COUNT] expected 120, parsed {len(fixed_objs)}")

    cnt_label = Counter(o["label"] for o in fixed_objs)
    cnt_lang  = Counter(o["meta"]["language"] for o in fixed_objs if isinstance(o.get("meta"),dict))
    expect_label = {"biz_quote":42,"tech_support":30,"policy_qa":14,"profile_update":12,"complaint":12,"other":10}
    expect_lang  = {"zh":84,"en":36}
    for k,v in expect_label.items():
        if cnt_label.get(k,0)!=v: errors.append(f"[DISTRIB] {k}: {cnt_label.get(k,0)} != {v}")
    for k,v in expect_lang.items():
        if cnt_lang.get(k,0)!=v: errors.append(f"[DISTRIB] lang {k}: {cnt_lang.get(k,0)} != {v}")

    if errors:
        print("=== ERRORS/WARNINGS ===", file=sys.stderr)
        for e in errors: print(e, file=sys.stderr)
        if args.fail_on_error: sys.exit(1)

    full_out = Path("data/intent/i_20250901_full.jsonl")
    full_out.parent.mkdir(parents=True, exist_ok=True)
    with full_out.open("w", encoding="utf-8") as w:
        for o in sorted(fixed_objs, key=lambda x: parse_id(x["id"])):
            w.write(json.dumps(o, ensure_ascii=False)+"\n")

    def write_range(p:Path, lo:int, hi:int):
        with p.open("w", encoding="utf-8") as w:
            for o in fixed_objs:
                idx = parse_id(o["id"])
                if lo<=idx<=hi: w.write(json.dumps(o, ensure_ascii=False)+"\n")

    write_range(outdir/"train.jsonl", 1, 100)
    write_range(outdir/"val.jsonl",   101, 110)
    write_range(outdir/"test.jsonl",  111, 120)

    print("== SUMMARY ==")
    print("labels:", dict(cnt_label))
    print("languages:", dict(cnt_lang))
    print(f"[OK] wrote {full_out}")
    print(f"[OK] wrote {outdir/'train.jsonl'}, {outdir/'val.jsonl'}, {outdir/'test.jsonl'}")

if __name__ == "__main__":
    main()
