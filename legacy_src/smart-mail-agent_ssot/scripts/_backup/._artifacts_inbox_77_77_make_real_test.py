import json,re,random
from pathlib import Path

random.seed(20250902)
ROOT=Path(".")
OUT = ROOT/"data/intent/external_realistic_test.jsonl"
PH  = {"EMAIL","PHONE","URL","ADDR","NAME","COMPANY","ORDER_ID","INVOICE_NO","AMOUNT"}

def okph(t):
    toks=set(re.findall(r"<([A-Z_]+)>", t))
    return toks.issubset(PH)

# 小工具
def subj(prefix_opts, core): 
    p=random.choice(["", "Re: ", "Fwd: ", ""])  # 偶爾帶前綴
    if random.random()<0.6: p=random.choice(prefix_opts)
    return f"{p}{core}" if p else f"{core}"

def amt_phrase():
    return random.choice([ "NT$<AMOUNT>", "USD <AMOUNT>" ])

def api_path():
    ver=random.choice(["v1","v2"])
    res=random.choice(["orders","items","users","invoices","payments"])
    return f"/{ver}/{res}"

def time_token():
    return random.choice(["EOD","EOW","10/12","11/05","by Friday"])

def label_row(i,label,lang,text):
    return {"id":f"rt-20250902-{i:04d}","text":text,"label":label,"meta":{"language":lang,"source":"realtest","confidence":1.0}}

rows=[]
seen=set()

# === biz_quote ===
def gen_biz_quote(n_zh,n_en):
    i=len(rows)
    zh_subj_pool=["Subject: 年費與SLA 詢價","Subject: 採購評估與SOW","Subject: 教育/非營利專案報價"]
    zh_bodies=[
        lambda: f"您好，預估 {random.choice([40,60,80,120,200])} seats，需報表+審計模組。請提供年度授權報價、SLA 等級與付款條件，並附 SOW 範圍與里程碑。總價請以 {amt_phrase()} 呈現，{time_token()} 前回覆。",
        lambda: f"我們評估 PoC 後導入，先 1 門市試點，Q4 擴到 {random.choice([8,12,20])} 店。請提供分級價格與一次性導入費，合計控制於 {amt_phrase()}。是否可提供 partner 折扣？",
        lambda: f"法務要求先看商務條款與違約金摘要。人數 {random.choice([35,45,55])}，請回覆三年 TCO（含維護）與 SLA。報價單請列單價/折扣/總價（{amt_phrase()}）。"
    ]
    en_subj_pool=["Subject: Pricing & SLA request","Subject: Quote with SOW","Subject: Education plan quote"]
    en_bodies=[
        lambda: f"Hi team, planning for {random.choice([40,60,90,120])} seats with audit/reporting. Please share annual pricing, SLA options, and SOW milestones. Grand total {amt_phrase()}, reply by {time_token()}.",
        lambda: f"We'll start with a {random.choice([1,2])}-store pilot then scale to {random.choice([10,20,30])}. Kindly provide tiered pricing and one-time setup. Target total {amt_phrase()}, payment terms 30 days.",
        lambda: f"Legal needs commercial terms before PO. Please include three-year TCO and SLA penalties. Quote should show unit, discount, and total ({amt_phrase()})."
    ]
    def add_one(lang):
        nonlocal i
        if lang=="zh":
            s=subj(["Re: ","Fwd: "], random.choice(zh_subj_pool)[9:])  # 保留 Subject:
            body=random.choice(zh_bodies)()
        else:
            s=subj(["Re: ","Fwd: "], random.choice(en_subj_pool))
            body=random.choice(en_bodies)()
        text=f"{s}\n\n{body}"
        k=("biz_quote",lang,text.lower())
        if okph(text) and k not in seen:
            rows.append(label_row(i,"biz_quote",lang,text)); seen.add(k); i+=1
    for _ in range(n_zh): add_one("zh")
    for _ in range(n_en): add_one("en")

# === tech_support ===
def gen_tech_support(n_zh,n_en):
    i=len(rows)
    def zh():
        env=random.choice(["prod","UAT","sandbox"])
        err=random.choice(["500","429"])
        s="Subject: 功能異常回報"
        body=f"Hi 支援，API {api_path()} 在 {env} 回 {err}。時段約 {random.choice(['10:20~10:35','昨晚 01:00-03:00','今早 09:00 前後'])}。請查 logs 並提供修復 ETA；若需我們提供請求 ID 請回覆（票號 <ORDER_ID>）。"
        return f"{s}\n\n{body}"
    def en():
        env=random.choice(["prod","UAT","sandbox"])
        err=random.choice(["500","429"])
        s="Subject: API issue"
        body=f"Hello Support, {api_path()} returns {err} in {env}. Affected window {random.choice(['10:20–10:35','01:00–03:00','around 09:00'])}. Please check logs and share ETA. Ticket <ORDER_ID>."
        return f"{s}\n\n{body}"
    def zh2():
        s="Subject: 登入/權限異常"
        body=f"同仁登入後儀表板空白，console 出現 CORS。昨晚剛更新白名單 IP。請協助檢查設定，必要時先提供 workaround，{time_token()} 前再測。"
        return f"{s}\n\n{body}"
    def en2():
        s="Subject: OTP/SSO sign-in problem"
        body=f"Users cannot sign in; OTP seems delayed. Any known issue with provider? Need workaround and ETA before {time_token()}."
        return f"{s}\n\n{body}"
    cands=[zh,zh2]; cands_en=[en,en2]
    for _ in range(n_zh):
        t=random.choice(cands)()
        k=("tech_support","zh",t.lower())
        if okph(t) and k not in seen:
            rows.append(label_row(len(rows),"tech_support","zh",t)); seen.add(k)
    for _ in range(n_en):
        t=random.choice(cands_en)()
        k=("tech_support","en",t.lower())
        if okph(t) and k not in seen:
            rows.append(label_row(len(rows),"tech_support","en",t)); seen.add(k)

# === policy_qa ===
def gen_policy(n_zh,n_en):
    def zh():
        s="Subject: 條款/退費流程確認"
        body=random.choice([
            f"若上線前取消，已開立發票是否需作廢或折讓？請提供流程與文件清單（含 PO/GRN、發票號 <INVOICE_NO>）。",
            f"提前終止是否需按剩餘月數比例計費？SLA 未達是否可無罰終止？請附正式政策連結 <URL>。",
            f"資料刪除與保存：終止後幾天內刪除？是否可依請求保留 90 天審計日誌？"
        ])
        return f"{s}\n\n{body}"
    def en():
        s="Subject: Refund/termination policy"
        body=random.choice([
            f"For pre go-live refunds, do we void or issue a credit note for invoice <INVOICE_NO>? Share steps and lead time.",
            f"Does SLA breach allow penalty-free termination? If not, how are pro-rated fees calculated?",
            f"Data retention/deletion after termination: official policy link <URL> appreciated."
        ])
        return f"{s}\n\n{body}"
    for _ in range(n_zh):
        t=zh(); k=("policy_qa","zh",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"policy_qa","zh",t)); seen.add(k)
    for _ in range(n_en):
        t=en(); k=("policy_qa","en",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"policy_qa","en",t)); seen.add(k)

# === profile_update ===
def gen_profile(n_zh,n_en):
    def zh():
        s="Subject: 資料變更申請"
        body=random.choice([
            f"請將帳單收件改為 <EMAIL>，並保留 <EMAIL> 在副本；下個計費週期生效。",
            f"發票抬頭改為 <COMPANY>，參考 PO 編號 <ORDER_ID>；本月開立請改用新抬頭。",
            f"白名單新增 IP：<ADDR>、<ADDR>。僅套用 UAT，prod 暫不變更。"
        ])
        return f"{s}\n\n{body}"
    def en():
        s="Subject: Contact/billing update"
        body=random.choice([
            f"Please change billing email to <EMAIL> and keep <EMAIL> in CC. Effective next cycle.",
            f"Update invoice header to <COMPANY>, reference PO <ORDER_ID>.",
            f"Add IP allowlist entries <ADDR> and <ADDR> for UAT only."
        ])
        return f"{s}\n\n{body}"
    for _ in range(n_zh):
        t=zh(); k=("profile_update","zh",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"profile_update","zh",t)); seen.add(k)
    for _ in range(n_en):
        t=en(); k=("profile_update","en",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"profile_update","en",t)); seen.add(k)

# === complaint ===
def gen_complaint(n_zh,n_en):
    def zh():
        s="Subject: 進度延宕與影響"
        body=random.choice([
            f"票號 <ORDER_ID> 開立多日仍無實質更新，尖峰時段仍受影響。請提供可交代的 ETA，否則我們將延後上線。",
            f"最近系統回應常超過 5 秒，營運端難以作業。請正面回應並給出改善計畫。"
        ])
        return f"{s}\n\n{body}"
    def en():
        s="Subject: Delay impact"
        body=random.choice([
            f"Ticket <ORDER_ID> has no actionable update; stores are impacted during peak hours. Need a realistic ETA.",
            f"Frequent reschedules create internal friction. Please commit to a stable plan and timeline."
        ])
        return f"{s}\n\n{body}"
    for _ in range(n_zh):
        t=zh(); k=("complaint","zh",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"complaint","zh",t)); seen.add(k)
    for _ in range(n_en):
        t=en(); k=("complaint","en",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"complaint","en",t)); seen.add(k)

# === other ===
def gen_other(n_zh,n_en):
    def zh():
        s="Subject: 先了解功能與導入"
        body=random.choice([
            f"目前僅蒐集資訊，想要產品功能簡介與成功案例連結 <URL>，暫不需報價。",
            f"能否安排 30 分鐘介紹，了解常見導入時程與資源配置？下週 {random.choice(['二','四'])} 下午可。"
        ])
        return f"{s}\n\n{body}"
    def en():
        s="Subject: Product overview"
        body=random.choice([
            f"We're exploring feasibility; a short deck and case studies link <URL> would help.",
            f"Could we schedule a 20–30 min intro to discuss rollout timelines? Pricing not required yet."
        ])
        return f"{s}\n\n{body}"
    for _ in range(n_zh):
        t=zh(); k=("other","zh",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"other","zh",t)); seen.add(k)
    for _ in range(n_en):
        t=en(); k=("other","en",t.lower())
        if okph(t) and k not in seen: rows.append(label_row(len(rows),"other","en",t)); seen.add(k)

# 產生：每類 20（zh 10 + en 10）= 120
gen_biz_quote(10,10)
gen_tech_support(10,10)
gen_policy(10,10)
gen_profile(10,10)
gen_complaint(10,10)
gen_other(10,10)

# 去重保證
def norm_key(r): 
    t=r["text"].lower()
    t=re.sub(r"\s+"," ",t)
    return (r["label"], r["meta"]["language"], t)

uniq=[]; s=set()
for r in rows:
    k=norm_key(r)
    if k not in s: s.add(k); uniq.append(r)

assert len(uniq)>=120, f"not enough unique samples: {len(uniq)}"
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",encoding="utf-8") as f:
    for r in uniq[:120]:
        f.write(json.dumps(r,ensure_ascii=False)+"\n")

# 統計
from collections import Counter
labs=Counter([r["label"] for r in uniq[:120]])
langs=Counter([r["meta"]["language"] for r in uniq[:120]])
print("[GEN]", OUT.as_posix(), "n=", len(uniq[:120]), "labs=", dict(labs), "langs=", dict(langs))
