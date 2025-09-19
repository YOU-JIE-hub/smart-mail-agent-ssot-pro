#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, random, argparse, re
from pathlib import Path
R = random.Random(42)
INTENTS = ["biz_quote","complaint","other","policy_qa","profile_update","tech_support"]
ENVS = ["prod","production","staging","test","dev"]
CUR  = ["NT$", "USD", "$"]

def write_jsonl(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)   # 關鍵：先建父目錄
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False)+"\n")

def rand_amount(): return f"{random.choice(CUR)}{R.randint(100,50000):,}"
def rand_date():
    if R.random()<0.6:
        y=R.choice([2024,2025]); m=R.randint(1,12); d=R.randint(1,28)
        return f"{y}/{m:02d}/{d:02d}"
    m=R.randint(1,12); d=R.randint(1,28); return f"{m}/{d}"

def make_row(it):
    amt=rand_amount(); dt=rand_date(); env=R.choice(ENVS)
    if it=="biz_quote": s=f"請問 {dt} 前能提供報價？{R.randint(5,80)} 位，約 {amt}。"
    elif it=="complaint": s=f"我們對上次服務不滿，{dt} 已寄出投訴表，請回覆。"
    elif it=="policy_qa": s="想了解 API 使用政策與資安規範，有沒有文件與 SLA 說明？"
    elif it=="profile_update": s="請協助更新公司聯絡資訊與發票抬頭，本周內完成即可。"
    elif it=="tech_support": s=f"{env} 無法登入，{dt} 仍持續，錯誤碼 401，請協助。"
    else: s="想索取產品簡介與 SDK 下載連結，謝謝。"
    if R.random()<0.2: s += f" Budget about {amt}."
    return {"text": s, "label": it}

def build(n):
    per = n // len(INTENTS)
    out = [make_row(it) for it in INTENTS for _ in range(per)]
    R.shuffle(out); return out

def build_kie_gold(test_path, out_path, max_n=120):
    rows=[json.loads(l) for l in Path(test_path).open(encoding="utf-8")]
    out=[]
    for r in rows[:max_n]:
        t=r["text"]; spans=[]
        m = re.search(r"\d{4}/\d{2}/\d{2}", t) or re.search(r"\d{1,2}/\d{1,2}", t)
        if m: spans.append({"start":m.start(),"end":m.end(),"label":"date_time"})
        for cur in CUR:
            i=t.find(cur)
            if i!=-1:
                j=i+len(cur)
                while j<len(t) and (t[j].isdigit() or t[j] in ",."): j+=1
                spans.append({"start":i,"end":j,"label":"amount"}); break
        low=t.lower()
        for e in ENVS:
            i=low.find(e)
            if i!=-1: spans.append({"start":i,"end":i+len(e),"label":"env"}); break
        out.append({"text":t,"spans":spans})
    write_jsonl(out_path, out)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--train", default="data/intent/train.jsonl")
    ap.add_argument("--val",   default="data/intent/val.jsonl")
    ap.add_argument("--test",  default="data/intent/test.jsonl")
    ap.add_argument("--kie-gold", default="data/kie/test.jsonl")
    ap.add_argument("--train-n", type=int, default=1200)
    ap.add_argument("--val-n",   type=int, default=300)
    ap.add_argument("--test-n",  type=int, default=300)
    a=ap.parse_args()
    train, val, test = build(a.train_n), build(a.val_n), build(a.test_n)
    write_jsonl(a.train, train); write_jsonl(a.val, val); write_jsonl(a.test, test)
    build_kie_gold(a.test, a.kie_gold, max_n=min(120,a.test_n))
    print(f"[DATA] train={len(train)} -> {a.train}")
    print(f"[DATA] val  ={len(val)} -> {a.val}")
    print(f"[DATA] test ={len(test)} -> {a.test}")
    print(f"[KIE ] gold -> {a.kie_gold}")
if __name__=="__main__": main()
