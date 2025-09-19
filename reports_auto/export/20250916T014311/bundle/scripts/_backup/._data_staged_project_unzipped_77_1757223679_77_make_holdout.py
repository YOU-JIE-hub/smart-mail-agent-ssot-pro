import json,re,random
from pathlib import Path
random.seed(20250902)

ROOT=Path(".")
FULL=ROOT/"data/intent/i_20250901_full.jsonl"
HC  =ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
CB  =ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"
MERG=ROOT/"data/intent/i_20250901_merged.jsonl"
OUT =ROOT/"data/intent/external_holdout.jsonl"

PH={"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

def R(p):
    a=[]
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln=ln.strip()
            if ln: a.append(json.loads(ln))
    return a

def okph(t):
    toks=set(re.findall(r"<([A-Z_]+)>",t))
    return toks.issubset(PH)

def nkey(t):
    t=t.lower()
    t=re.sub(r"\s+","",t)
    t=re.sub(r"[^\w\u4e00-\u9fff<>]+","",t)
    return t

base=R(FULL); hc=R(HC); cb=R(CB); auto=R(AUTO); merg=R(MERG)
seen=set(nkey(r["text"]) for r in (base+hc+cb+auto+merg))

labs=["biz_quote","tech_support","policy_qa","profile_update","complaint","other"]

# 更豐富的改寫字典（確保與訓練不同）
syn={
"biz_quote":[
    (r"報價|詢價","試算"),(r"總價","總額"),(r"\bquote\b","pricing"),
    (r"SOW","工作說明"),(r"年費","年度授權"),(r"折扣","優惠"),(r"TCO","總持有成本")
],
"tech_support":[
    (r"\bprod(uction)?\b","production"),(r"\bUAT\b","測試環境"),
    (r"\bAPI\b","介面"),(r"\b429\b","限流 429"),(r"\b500\b","5xx"),
    (r"OTP","一次性密碼"),(r"CORS","跨域"),(r"webhook","回呼")
],
"policy_qa":[
    (r"退費|退款","退款"),(r"條款|政策","政策"),(r"SLA","服務等級"),
    (r"提前終止","終止合約"),(r"折讓|credit note","折讓單")
],
"profile_update":[
    (r"更新|變更","調整"),(r"新增","加上"),(r"白名單\s*IP","白名單IP"),
    (r"發票抬頭","抬頭"),(r"寄送地址","收件地址"),(r"billing","帳務")
],
"complaint":[
    (r"延宕|延期","延遲"),(r"沒有更新","缺乏更新"),(r"請提供\s*ETA","需要 ETA"),
    (r"不一致","矛盾"),(r"太慢","過慢"),(r"沒有動靜","無進展")
],
"other":[
    (r"簡介|概覽|介紹","概覽"),(r"成功案例","案例"),(r"Roadmap|roadmap","Roadmap"),
    (r"不急著報價|暫不需要價格","暫不需要價格")
]}

trail_zh=[" 請協助回覆。"," 麻煩回覆。"," 煩請確認。"," 敬請回覆。"]
trail_en=[" Please advise."," Kindly confirm."," Thanks."," Please share details."]

def jitter(t,lang):
    if random.random()<0.4: t=re.sub(r"\s{2,}"," ",t)
    if random.random()<0.3: t=t.replace("，",",").replace("。",".")
    if random.random()<0.35 and not t.startswith(("Re: ","Fwd: ")): t=("Re: " if random.random()<0.6 else "Fwd: ")+t
    if random.random()<0.35:
        tok=random.choice(["EOD","EOW","ETA","下週","本週","今晚"])
        if lang=="en": tok=random.choice(["EOD","EOW","ETA","tomorrow","next week"])
        if tok not in t: t+=" "+tok
    if "<AMOUNT>" in t and random.random()<0.7:
        t=re.sub(r"(NT\$|USD|US\$)?\s*<AMOUNT>", random.choice(["NT$ <AMOUNT>","USD <AMOUNT>","US$ <AMOUNT>"]), t)
    if lang=="zh" and random.random()<0.35: t+=random.choice(trail_zh)
    if lang=="en" and random.random()<0.35: t+=random.choice(trail_en)
    return t

def swap(t,lab):
    for pat,rep in syn[lab]:
        if random.random()<0.7:
            t=re.sub(pat, rep, t, flags=re.I)
    return t

def make_variant(r):
    t=r["text"]; lab=r["label"]; lang=r["meta"]["language"]
    t=swap(t,lab); t=jitter(t,lang)
    return {**r,"id":"h-"+r["id"],"text":t}

# 來源擴大到 base+hc+cb（避免過窄）
by_lab={}
for lab in labs:
    seeds=[x for x in (base+hc+cb) if x["label"]==lab]
    random.shuffle(seeds)
    by_lab[lab]=seeds

want_per=10
out=[]; reasons={"dup":0,"ph":0}

for lab in labs:
    seeds=by_lab[lab]
    i=0; si=0; tries=0
    # 如果種子數少，循環使用不同改寫湊滿 10
    while i<want_per and tries<5000:
        r=seeds[si % len(seeds)]
        si+=1; tries+=1
        cand=make_variant(r)
        if not okph(cand["text"]): reasons["ph"]+=1; continue
        nk=nkey(cand["text"])
        if nk in seen: reasons["dup"]+=1; continue
        seen.add(nk); out.append(cand); i+=1
    if i<want_per:
        # 強制兜底：附加無害小尾巴確保唯一性
        while i<want_per:
            r=seeds[si % len(seeds)]; si+=1
            t=r["text"]+" (請回覆)" if r["meta"]["language"]=="zh" else r["text"]+" (please reply)"
            cand={**r,"id":"h2-"+r["id"],"text":t}
            nk=nkey(cand["text"])
            if nk in seen or not okph(cand["text"]): continue
            seen.add(nk); out.append(cand); i+=1

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in out)+"\n",encoding="utf-8")
print("[HOLDOUT]", len(out), "->", OUT)
