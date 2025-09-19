#!/usr/bin/env python3
import argparse, json, random, re
from pathlib import Path
R=random.Random(42)
FW = str.maketrans("0123456789.$,.", "０１２３４５６７８９．＄，．")  # 半/全形替換
def aug_amount(s):
    # $→＄、逗號→全形、隨機加小數
    s2 = s.replace("$","＄").replace(",", "，")
    if re.search(r"\d", s2) and R.random()<0.4:
        s2 = re.sub(r"([0-9]+)", lambda m: m.group(1)+("." if R.random()<0.5 else "．")+str(R.randint(1,99)), s2, count=1)
    if R.random()<0.3: s2 = s2.translate(FW)
    return s2
def aug_date(s):
    s2 = re.sub(r"(\d{4})/(\d{1,2})/(\d{1,2})", r"\1.\2.\3", s)
    s2 = re.sub(r"(\d{1,2})/(\d{1,2})", r"\1月\2日", s2)
    if R.random()<0.3: s2 = re.sub(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", r"\1年\2月\3日", s2, count=1)
    return s2
def aug_env(s):
    s2 = re.sub(r"\bproduction\b", "prd", s, flags=re.I)
    s2 = re.sub(r"\bstaging\b", "stg", s2, flags=re.I)
    return s2
def aug_line(o):
    t=o.get("text","")
    # 嘗試針對金額與日期與環境做替換
    t2=aug_amount(t); t2=aug_date(t2); t2=aug_env(t2)
    if t2!=t: return {"text":t2,"label":o.get("label")}
    return None
def run(inp, outp, ratio):
    import math
    rows=[json.loads(l) for l in Path(inp).open(encoding="utf-8")]
    n_aug=max(1, int(len(rows)*ratio))
    picked=R.sample(range(len(rows)), k=min(n_aug,len(rows)))
    out=Path(outp); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w",encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
        for idx in picked:
            aug=aug_line(rows[idx])
            if aug: f.write(json.dumps(aug,ensure_ascii=False)+"\n")
    print(f"[AUG] base={len(rows)}  added≈{len(picked)} -> {out}")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in_jsonl", required=True)
    ap.add_argument("--out_jsonl", required=True)
    ap.add_argument("--ratio", type=float, default=0.5)  # 50% 行做一個變體
    args=ap.parse_args(); run(args.in_jsonl, args.out_jsonl, args.ratio)
if __name__=="__main__": main()
