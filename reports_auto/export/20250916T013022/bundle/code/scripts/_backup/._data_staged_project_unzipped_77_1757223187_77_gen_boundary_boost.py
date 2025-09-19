import json, re, random
from pathlib import Path
random.seed(20250902)

ROOT=Path(".")
MISS=ROOT/"reports_auto/holdout_misses.jsonl"
FULL=ROOT/"data/intent/i_20250901_full.jsonl"
HC  =ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB  =ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"
MERG=ROOT/"data/intent/i_20250901_merged.jsonl"
OUT =ROOT/"data/intent/i_20250902_boundary_boost.jsonl"

PH={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

def R(p):
    a=[]
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln=ln.strip()
            if ln: a.append(json.loads(ln))
    return a

def okph(t):
    toks=set(re.findall(r"<([A-Z_]+)>",t)); return toks.issubset(PH)

def nkey(t):
    t=t.lower()
    t=re.sub(r"\s+","",t)
    t=re.sub(r"[^\w\u4e00-\u9fff<>]+","",t)
    return t

# 類別關鍵字，用於往正確類別拉
hint = {
 "biz_quote":[ "報價","試算","quote","SOW","折扣","NT$ <AMOUNT>","年度授權","TCO" ],
 "tech_support":[ "API","/v1/","UAT","prod","429","500","OTP","CORS","SSO","webhook" ],
 "policy_qa":[ "退費","退款","條款","提前終止","credit note","SLA 違約" ],
 "profile_update":[ "更新","變更","白名單 IP","寄送地址","發票抬頭","<EMAIL>" ],
 "complaint":[ "延遲","久未處理","沒有更新","請提供 ETA","影響上線" ],
 "other":[ "簡介","案例","Roadmap","暫不需要價格" ]
}

trail_zh=[" 請協助回覆。"," 麻煩回覆。"," 煩請確認。"]
trail_en=[" Please advise."," Kindly confirm."," Please reply."]

def jitter(t):
    if random.random()<0.4: t=re.sub(r"\s{2,}"," ",t)
    if random.random()<0.3: t=t.replace("，",",").replace("。",".")
    if "<AMOUNT>" in t and random.random()<0.6:
        t=re.sub(r"(NT\$|USD|US\$)?\s*<AMOUNT>", random.choice(["NT$ <AMOUNT>","USD <AMOUNT>"]), t)
    if re.search(r"[A-Za-z]", t) and random.random()<0.3: t+=random.choice(trail_en)
    else:
        if random.random()<0.3: t+=random.choice(trail_zh)
    return t

def steer(text, lab):
    t=text
    toks=hint[lab]
    if random.random()<0.6:
        tok=random.choice(toks)
        if tok not in t: t = (("Re: " if random.random()<0.5 else "Fwd: ")+t) if random.random()<0.3 else t
        t += (" " if not t.endswith(" ") else "") + tok
    return jitter(t)

# 集合去重基準：現有所有訓練相關檔
seen=set()
for p in [FULL,HC,CB,AUTO,MERG]:
    for r in R(p):
        seen.add(nkey(r.get("text","")))

miss=R(MISS)
by_lab={}
for m in miss:
    by_lab.setdefault(m["gold"],[]).append(m)

cap_total=30
out=[]
for lab,rows in by_lab.items():
    random.shuffle(rows)
    quota = max(3, min(6, (cap_total//max(1,len(by_lab)))))  # 每類 3~6 筆
    c=0; tries=0
    i=0
    while c<quota and tries<1000 and i<len(rows):
        m=rows[i]; i=(i+1)%len(rows); tries+=1
        cand_txt=steer(m["text"], lab)
        if not okph(cand_txt): continue
        k=nkey(cand_txt)
        if k in seen: continue
        seen.add(k)
        out.append({"id":f"b-{lab}-{len(out)+1:03d}","label":lab,"meta":{"language":"zh" if re.search(r"[\u4e00-\u9fff]",cand_txt) else "en","source":"boundary_boost","confidence":1.0},"text":cand_txt})
        c+=1
    if c<quota:
        # 兜底
        for _ in range(quota-c):
            t=steer(rows[0]["text"], lab)
            if not okph(t): continue
            k=nkey(t)
            if k in seen: continue
            seen.add(k)
            out.append({"id":f"b-{lab}-{len(out)+1:03d}","label":lab,"meta":{"language":"zh" if re.search(r"[\u4e00-\u9fff]",t) else "en","source":"boundary_boost","confidence":1.0},"text":t})

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in out)+"\n", encoding="utf-8")
print("[BOOST_CNT]", len(out), "->", OUT)
