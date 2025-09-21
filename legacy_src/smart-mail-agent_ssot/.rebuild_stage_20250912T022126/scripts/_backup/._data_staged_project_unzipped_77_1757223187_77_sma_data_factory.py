#!/usr/bin/env python3
# v3 — 結構驅動郵件生成器（穩定配額 + 自動放寬去重 + 多結構變體）
from __future__ import annotations
import json, random, re, math, hashlib, argparse
from pathlib import Path
from datetime import date
from collections import Counter

# ===== 參數 =====
DEF_TOTAL=1000; DEF_SPAM=0.55; DEF_ZH=0.50
DEF_LEN={"short":0.25,"medium":0.45,"long":0.30}
DEF_MULTI=0.28; DEF_SEED=4242

# ===== 小工具 =====
def ngrams(s,n=3): return [s[i:i+n] for i in range(max(0,len(s)-n+1))]
def normalize(s):
    s=s.lower(); s=re.sub(r'\s+',' ',s); s=re.sub(r'\d','#',s); s=re.sub(r'[^\w\u4e00-\u9fff]+',' ',s)
    return s.strip()
def simhash(tokens):
    v=[0]*64
    for t in tokens:
        h=int(hashlib.md5(t.encode('utf-8')).hexdigest(),16)
        for i in range(64): v[i]+= 1 if (h>>i)&1 else -1
    f=0
    for i in range(64):
        if v[i]>0: f|=(1<<i)
    return f
def hamming(a,b): return (a^b).bit_count()
def jaccard(a,b):
    A=set(a); B=set(b)
    return 0.0 if not A or not B else len(A&B)/len(A|B)

def ensure_len(bucket, subj, body, lang, mp):
    lo={"short":15,"medium":41,"long":121}[bucket]
    def words(x): return max(1, len(re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]+',' ',x).split()))
    fillers_zh=[
        "若有疑問請回覆此信。","造成不便敬請見諒。","此為系統自動通知。","如需協助請洽客服。","請留存此郵件備查。"
    ]
    fillers_en=[
        "Please review and respond.","We appreciate your prompt attention.","This is an automated notice.",
        "Contact support if needed.","Please keep this email for your records."
    ]
    pool = fillers_zh if lang=="zh" else fillers_en
    sep = "\n\n" if mp else "\n"
    while words(subj+" "+body) < lo:
        body += sep + random.choice(pool)
    return body

# ===== 槽位與素材 =====
EN_FIRST=["Alice","Bob","Charlie","David","Emily","Frank","Grace","Hannah","Ivan","Julia","Kevin","Laura","Michael","Nina","Oscar","Peter","Quinn","Robert","Sophie","Tom","Uma","Victor","Wendy","Xavier","Yvonne","Zack"]
EN_LAST =["Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Garcia","Wilson","Anderson","Taylor","Thomas","Moore","Martin","Lee","Thompson","White","Harris","Clark","Lewis","Walker","Young"]
ZH_NAME=["王小明","陳雅婷","張偉倫","林子涵","黃郁庭","吳佩珊","徐建安","蔡欣怡","劉柏翰","楊淑芬","許家瑋","鄭伊婷","謝東霖","洪詠晴","郭冠宇","曾怡君","莊博彥","詹于庭","李嘉豪","周文婷"]
CO=["acme","megacorp","globalcorp","contoso","citypower","ispnet","healthcare","utilityco","anycompany","techfirm","xyzinc","infotech","shopfast","smartcloud","telecomco","safebank","fintrust"]
HAM_DOM=[f"{c}.com" for c in CO]+["company.com","service.com","support.com","billing.com","hr.com","admin.com","it.com","sales.com","example.com","example.org","example.net","bank.com","cloud.com","corp.tw","corp.com.tw"]
SUSP_TLD=["zip","xyz","top","click","link","quest","gq","cf","ml","work","rest"]
PHISH_BASE=["account-sec","login-update","verify-now","reset-center","id-validate","customer-care","billing-alert","delivery-update","lottery-claim","wallet-update","auth-check","secure-id"]
SAFE_HOST=["portal","www","support","docs"]; SAFE_PATH=["help","login","unsubscribe","status","pay","docs","kb","support"]

def en_name(): return f"{random.choice(EN_FIRST)} {random.choice(EN_LAST)}"
def zh_name(): return random.choice(ZH_NAME)
def ham_dom(): return random.choice(HAM_DOM)
def susp_url(): return f"http://{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789',k=8))}"
def safe_url(): return f"https://{random.choice(SAFE_HOST)}.{random.choice(CO)}.com/{random.choice(SAFE_PATH)}"
def invno(): return str(random.randint(10000,99999))
def trno():  return str(random.randint(10000,99999))
def amt_usd(): return random.choice([49,59,75,99,120,250,400,500,799,1200])
def amt_ntd(): return random.choice([150,199,299,399,499,599,799,1200,1500,2500])

def blk_bulleted(lines): return "\n".join(random.choice(["- ","• "])+ln for ln in lines)
def blk_table(rows): return "\n".join([f"{k}: {v}" for k,v in rows])
def blk_qna(pairs): return "\n".join([f"Q: {q}\nA: {a}" for q,a in pairs])

def add_forward(body, lang="en"):
    if lang=="en":
        hdr = f"----- Forwarded message -----\nFrom: {en_name()} <notice@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}>\nSubject: Update your details\nDate: 2025-08-10"
        tail= random.choice(["We noticed changes on your account.","Security check pending."])
    else:
        hdr = f"---------- 轉寄郵件 ----------\nFrom: {zh_name()} <notice@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}>\nSubject: 帳務異常通知\nDate: 2025-08-10"
        tail= random.choice(["請更新個人資料以維持服務。","安全檢查待完成。"])
    return body + "\n\n" + hdr + "\n" + tail
def add_reply(body, lang="en"):
    return body + ("\n\n----- Original Message -----\nI had an issue with my invoice last month."
                   if lang=="en" else "\n\n----- 原始郵件 -----\n上月帳單折扣未套用，請協助確認。")

# ===== Spam 變體（每型多路徑） =====
def spam_en_cred(lb, mp):
    variant=random.randint(1,3)
    if variant==1:
        subj="Unusual sign-in attempt"
        body=f"Dear Customer,\nWe blocked a suspicious login.\nAction: verify at {susp_url()} within 24h.\nSecurity"
    elif variant==2:
        subj="Account Security Alert"
        body=blk_qna([("Why did I get this?","We detected unusual activity."),("What to do?","Verify your identity at the link.")]) + f"\nLink: {susp_url()}"
    else:
        subj="Verify your account now – action needed"
        body="Hello,\n"+blk_bulleted(["Identity check pending","Service will pause without verification"])+f"\nVerify: {susp_url()}\nRegards"
    if mp: body=add_forward(body,"en")
    return subj,body,[]

def spam_en_pay(lb, mp):
    variant=random.randint(1,3)
    subj="Payment verification needed"
    if variant==1:
        body=f"Hello,\nYour recent payment could not be verified.\nConfirm here: {susp_url()}.\nAmount due: ${amt_usd()}.\nThank you."
    elif variant==2:
        body="Billing Notice\n\n"+blk_table([("Status","Hold"),("Reason","Verification failed"),("Resolve",susp_url())])+"\nFinance"
    else:
        body="Dear user,\nWe could not match your billing details.\n"+blk_bulleted(["Card mismatch","Address requires update"])+f"\nProceed: {susp_url()}"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def spam_en_invoice(lb, mp):
    inv=invno(); ext=random.choice(["zip","js","htm"])
    subj=f"Invoice {inv} – payment required"
    variant=random.randint(1,3)
    if variant==1:
        body="Dear Customer,\nPlease see attached invoice.\n"+blk_table([("Invoice",inv),("Status","Overdue")])+f"\n(Attachment: Invoice_{inv}.{ext})\nFinance"
    elif variant==2:
        body=f"Reminder: invoice {inv} is overdue.\nOpen attachment to review terms.\nAttachment: Invoice_{inv}.{ext}"
    else:
        body=f"Payment overdue for invoice {inv}.\nDownload form: Invoice_{inv}.{ext}\nFinance Desk"
    if mp: body=add_forward(body,"en")
    return subj,body,[f"Invoice_{inv}.{ext}"]

def spam_en_delivery(lb, mp):
    tr=trno(); ext=random.choice(["zip","htm"])
    subj=f"Delivery failed – action required ({tr})"
    variant=random.randint(1,2)
    if variant==1:
        body=f"Dear Customer,\nPackage {tr} needs address confirmation.\nUpdate: {susp_url()} (48h)\nDelivery"
    else:
        body=blk_table([("Package",tr),("Status","Failed attempt"),("Next step",susp_url())])+"\n\nSupport Team"
    if mp: body=add_reply(body,"en")
    return subj,body,[f"Label_{tr}.{ext}"]

def spam_en_crypto(lb, mp):
    ret=random.choice([30,35,45,50]); subj=f"Exclusive crypto opportunity – {ret}% monthly returns"
    variant=random.randint(1,3)
    if variant==1:
        body="Dear Investor,\n"+blk_bulleted([f"{ret}% monthly target","Expert-led strategies","Withdraw anytime"])+f"\nJoin: {susp_url()}"
    elif variant==2:
        body=blk_table([("Strategy","Managed fund"),("Target",f"{ret}%/month"),("Access",susp_url())])+"\nTeam"
    else:
        body="Hi,\nWe open a small window for new members.\nLearn more: "+susp_url()
    if mp: body=add_forward(body,"en")
    return subj,body,[]

def spam_en_prize(lb, mp):
    subj="FINAL NOTICE: Claim your prize"
    body="Congratulations!\nYour email won a cash prize.\nReply with full name and address to process.\nPromotions"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def spam_zh_cred(lb, mp):
    subj=random.choice(["重要：請立即驗證您的帳戶","安全提醒：異常登入"])
    variant=random.randint(1,3)
    if variant==1:
        body=f"親愛的用戶：\n偵測到異常活動，請於24小時內至 {susp_url()} 完成驗證。\n客服中心"
    elif variant==2:
        body="提醒：\n"+blk_bulleted(["近期有異常登入跡象","需確認身份以維持服務"])+f"\n驗證連結：{susp_url()}"
    else:
        body=blk_table([("狀態","待驗證"),("期限","24 小時"),("連結",susp_url())])+"\n資訊安全組"
    if mp: body=add_forward(body,"zh")
    return subj,body,[]

def spam_zh_pay(lb, mp):
    subj="付款驗證失敗：請更新帳務資訊"
    variant=random.randint(1,2)
    if variant==1:
        body=f"您好：\n最近一次扣款未成功。請至 {susp_url()} 更新付款資料。\n本次應繳：NT${amt_ntd()}。\n感謝配合。"
    else:
        body="帳務通知：\n"+blk_table([("狀態","暫停"),("原因","驗證失敗"),("處理",susp_url())])+"\n財務部"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

def spam_zh_invoice(lb, mp):
    inv=invno(); ext=random.choice(["zip","js","htm"])
    subj=f"發票通知（{inv}）- 逾期未繳"
    variant=random.randint(1,2)
    if variant==1:
        body=f"尊敬的客戶：\n附件為本期發票（{inv}），目前顯示逾期，請儘速處理。\n（附件：{inv}.{ext}）\n財務部"
    else:
        body="催繳提醒：\n"+blk_table([("發票編號",inv),("狀態","逾期"),("付款","請參閱附件")])+f"\n附件：{inv}.{ext}"
    if mp: body=add_forward(body,"zh")
    return subj,body,[f"{inv}.{ext}"]

def spam_zh_delivery(lb, mp):
    tr=trno(); ext=random.choice(["zip","htm"])
    subj=f"【配送異常】包裹待處理（{tr}）"
    body=random.choice([
        f"您好：\n包裹（{tr}）因地址不全暫存本站，請於48小時內至 {susp_url()} 確認資訊並安排重新投遞。\n物流客服",
        blk_table([("包裹",tr),("狀態","投遞失敗"),("下一步",susp_url())])+"\n客服中心"
    ])
    if mp: body=add_reply(body,"zh")
    return subj,body,[f"通知單_{tr}.{ext}"]

def spam_zh_crypto(lb, mp):
    subj="高收益投資方案：月報酬 35%"
    body="投資人您好：\n"+blk_bulleted(["月報酬 35%","專家團隊操作","可隨時贖回"])+f"\n詳情：{susp_url()}\n理財顧問團隊"
    if mp: body=add_forward(body,"zh")
    return subj,body,[]

def spam_zh_prize(lb, mp):
    subj="恭喜中獎！請立即完成領取"
    body="您好：\n您在活動中獲得獎金，請回覆姓名與聯絡方式以便辦理。\n活動小組"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

# ===== Ham 變體 =====
def ham_en_invoice(lb, mp):
    inv=invno()
    subj=f"Invoice #{inv} for September"
    variant=random.randint(1,2)
    if variant==1:
        body=f"Hello,\nPlease find attached the invoice #{inv}. Total is ${amt_usd()}, payable by Oct 10, {date.today().year}.\nAccounts Receivable"
    else:
        body="Billing Info\n\n"+blk_table([("Invoice",inv),("Due",f"Oct 10, {date.today().year}"),("Total",f"${amt_usd()}")])+"\nAR Team"
    if mp: body=add_reply(body,"en")
    return subj,body,[f"Invoice_{inv}.pdf"]

def ham_en_minutes(lb, mp):
    subj=f"Meeting Minutes – Project Update ({date.today().strftime('%Y-%m-%d')})"
    body="Hi Team,\n"+blk_bulleted(["Timeline adjusted","Risks reviewed","Next steps assigned"])+ "\nPlease see attached minutes.\nBest,\nPM"
    if mp: body=add_forward(body,"en")
    return subj,body,[f"MeetingMinutes_{date.today().strftime('%Y-%m-%d')}.docx"]

def ham_en_support(lb, mp):
    subj="RE: Your support ticket has been resolved"
    body="Dear Customer,\nWe have resolved your issue and refreshed your account settings.\nIf anything else comes up, reply to this email.\nSupport Team"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def ham_en_announce(lb, mp):
    subj="Official Notice: System Maintenance"
    body="To all employees,\nWe will perform scheduled maintenance next Friday.\nPlease review the attached memo.\nIT Department"
    if mp: body=add_forward(body,"en")
    return subj,body,["Maintenance_Memo.pdf"]

def ham_en_marketing(lb, mp):
    subj="October Newsletter – Updates and Deals"
    body="Dear Customer,\nThis month's updates and offers:\n"+blk_bulleted(["New arrivals","Top picks","15% off with code"])+f"\nUnsubscribe: {safe_url()}"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def ham_zh_invoice(lb, mp):
    inv=invno()
    subj=f"繳費通知：發票 {inv}"
    body=f"親愛的客戶：\n附件為本期發票（{inv}），金額 NT${amt_ntd()}，請於截止日前完成繳費。\n帳務中心"
    if mp: body=add_reply(body,"zh")
    return subj,body,[f"{inv}.pdf"]

def ham_zh_minutes(lb, mp):
    subj=f"會議紀錄：專案更新（{date.today().strftime('%Y%m%d')}）"
    body="各位好：\n"+blk_bulleted(["調整時程","風險盤點","指派後續任務"])+ "\n詳情請見附件，若有補充請回覆。\nPM"
    if mp: body=add_forward(body,"zh")
    return subj,body,[f"Meeting_{date.today().strftime('%Y%m%d')}.docx"]

def ham_zh_support(lb, mp):
    subj="RE: 您的問題已處理完成"
    body="您好：\n我們已完成問題排除並重新整理您的帳戶設定，服務應已恢復。\n如需協助請回覆。\n客服中心"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

def ham_zh_announce(lb, mp):
    subj="公司公告：系統維護排程"
    body="全體同仁好：\n下週五進行系統維護，請參閱附件了解作業時間與影響範圍。\n資訊部"
    if mp: body=add_forward(body,"zh")
    return subj,body,["維護公告.pdf"]

def ham_zh_marketing(lb, mp):
    subj="本月電子報｜優惠與新品"
    body=f"親愛的用戶：\n本期精選內容與優惠請見內文。如欲退訂：{safe_url()}\n行銷小組"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

SPAM_EN={"phishing_credentials":spam_en_cred,"phishing_payment":spam_en_pay,"fake_invoice":spam_en_invoice,"fake_delivery":spam_en_delivery,"investment_crypto":spam_en_crypto,"lottery_prize":spam_en_prize}
SPAM_ZH={"phishing_credentials":spam_zh_cred,"phishing_payment":spam_zh_pay,"fake_invoice":spam_zh_invoice,"fake_delivery":spam_zh_delivery,"investment_crypto":spam_zh_crypto,"lottery_prize":spam_zh_prize}
HAM_EN ={"invoice_legit":ham_en_invoice,"meeting_minutes":ham_en_minutes,"customer_service":ham_en_support,"announcement":ham_en_announce,"marketing_optout":ham_en_marketing}
HAM_ZH ={"invoice_legit":ham_zh_invoice,"meeting_minutes":ham_zh_minutes,"customer_service":ham_zh_support,"announcement":ham_zh_announce,"marketing_optout":ham_zh_marketing}

# ===== 主流程（動態配額 + 自動放寬去重） =====
def alloc(total, kinds, min_ratio):
    need=math.floor(total*min_ratio)
    d={k:need for k in kinds}; left=total-need*len(kinds); i=0
    while left>0: d[kinds[i%len(kinds)]]+=1; left-=1; i+=1
    return Counter(d)

def uniq_ok(subj, body, feats, exact, stage):
    # stage 0: H<=3 & J>=0.88  or J>=0.93   (嚴)
    # stage 1: H<=4 & J>=0.87  or J>=0.94
    # stage 2: H<=5 & J>=0.85  or J>=0.95
    # stage 3: H<=6 & J>=0.83  or J>=0.96   (較鬆，但仍避免近重)
    H=[3,4,5,6][stage]; JA=[0.88,0.87,0.85,0.83][stage]; JB=[0.93,0.94,0.95,0.96][stage]
    norm=normalize(subj+"\n"+body); grams=ngrams(norm,3); sh=simhash(grams) if grams else 0
    key=hashlib.sha256(norm.encode('utf-8')).hexdigest()
    if key in exact: return False
    for n2,g2,sh2 in feats:
        ham=hamming(sh,sh2)
        if (ham<=H and jaccard(grams,g2)>=JA) or jaccard(grams,g2)>=JB:
            return False
    exact.add(key); feats.append((norm,grams,sh)); return True

def build(N, spam_ratio, zh_ratio, len_ratio, multi_ratio, seed):
    random.seed(seed)
    SPAM_N=round(N*spam_ratio); HAM_N=N-SPAM_N
    # 初始化配額
    lang_quota=Counter({"zh":round(N*zh_ratio),"en":N-round(N*zh_ratio)})
    len_quota=Counter({k:round(N*v) for k,v in len_ratio.items()})
    multi_quota=Counter({"mp":round(N*multi_ratio),"sp":N-round(N*multi_ratio)})

    spam_k=list(SPAM_EN.keys()); ham_k=list(HAM_EN.keys())
    spam_quota=alloc(SPAM_N, spam_k, 0.08)
    ham_quota =alloc(HAM_N, ham_k, 0.10)

    entries=[]; feats=[]; exact=set(); sid=1; hid=1

    ATTEMPT_MAX=N*200
    stage=0; stage_step=max(1, N*4)  # 每 4N 次放寬一檔
    for tries in range(ATTEMPT_MAX):
        if len(entries)>=N: break
        if tries>0 and tries % stage_step == 0 and stage<3:
            stage+=1

        # 根據剩餘配額選擇屬性
        label = "spam" if (sum(spam_quota.values())>0 and (len(entries)<SPAM_N or sum(ham_quota.values())==0)) else "ham"
        lang  = "zh" if (lang_quota["zh"]>0 and (lang_quota["zh"]>=lang_quota["en"])) else ("en" if lang_quota["en"]>0 else random.choice(["zh","en"]))
        lb    = max(len_quota, key=lambda k: len_quota[k]) if sum(len_quota.values())>0 else random.choice(list(DEF_LEN.keys()))
        mp    = True if (multi_quota["mp"]>0 and (multi_quota["mp"]>=multi_quota["sp"])) else (False if multi_quota["sp"]>0 else bool(random.getrandbits(1)))

        # subtype 選擇（優先用尚有配額的）
        if label=="spam":
            elig=[k for k,c in spam_quota.items() if c>0] or spam_k
            subtype=random.choice(elig); gen = SPAM_EN if lang=="en" else SPAM_ZH
        else:
            elig=[k for k,c in ham_quota.items() if c>0] or ham_k
            subtype=random.choice(elig); gen = HAM_EN if lang=="en" else HAM_ZH

        subj, body, att = gen[subtype](lb, mp)
        frm = (f"no-reply@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}"
               if label=="spam" else
               f"{random.choice(['billing','support','hr','admin','it','service','news'])}@{ham_dom()}")

        body = ensure_len(lb, subj, body, lang, mp)
        to   = random.choice(["user@example.com", f"team@{random.choice(CO)}.com", f"all.staff@{random.choice(CO)}.com"])

        if not uniq_ok(subj, body, feats, exact, stage): 
            continue

        # 被接受才扣配額
        if label=="spam" and spam_quota[subtype]>0: spam_quota[subtype]-=1
        if label=="ham"  and ham_quota[subtype]>0:  ham_quota[subtype]-=1
        if lang_quota[lang]>0: lang_quota[lang]-=1
        if len_quota[lb]>0: len_quota[lb]-=1
        if mp and multi_quota["mp"]>0: multi_quota["mp"]-=1
        if (not mp) and multi_quota["sp"]>0: multi_quota["sp"]-=1

        _id=("S"+f"{sid:06d}") if label=="spam" else ("H"+f"{hid:06d}")
        if label=="spam": sid+=1
        else: hid+=1
        entries.append({"id":_id,"subject":subj,"body":body,"from":frm,"to":to,"attachments":att,"label":label})

    if len(entries)<N:
        raise RuntimeError(f"Failed to generate enough unique entries: {len(entries)}/{N}. Try adjusting --seed or thresholds.")

    # 統計
    def lang_detect(e): return "zh" if re.search(r'[\u4e00-\u9fff]', e["subject"]+" "+e["body"]) else "en"
    def len_bucket(e):
        w=len(re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]+',' ', (e["subject"]+" "+e["body"])).split())
        return "short" if w<=40 else ("medium" if w<=120 else "long")
    label_cnt=Counter([e["label"] for e in entries]); lang_cnt=Counter([lang_detect(e) for e in entries]); length_cnt=Counter([len_bucket(e) for e in entries])
    mp_ratio=sum(1 for e in entries if "\n\n" in e["body"] or "Forwarded message" in e["body"] or "轉寄" in e["body"])/len(entries)
    stats={"label":dict(label_cnt),"lang":dict(lang_cnt),"length":dict(length_cnt),"multi_para_ratio":round(mp_ratio,3)}
    return entries, stats

def split_and_save(entries, outdir:Path):
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir/"all.jsonl").open("w",encoding="utf-8") as f:
        for e in entries: f.write(json.dumps(e, ensure_ascii=False)+"\n")
    spam=[e for e in entries if e["label"]=="spam"]; ham=[e for e in entries if e["label"]=="ham"]
    random.shuffle(spam); random.shuffle(ham)
    def cut(lst):
        n=len(lst); ntr=round(0.8*n); nva=round(0.1*n); return lst[:ntr], lst[ntr:ntr+nva], lst[ntr+nva:]
    s_tr,s_va,s_te = cut(spam); h_tr,h_va,h_te = cut(ham)
    tr=s_tr+h_tr; va=s_va+h_va; te=s_te+h_te
    random.shuffle(tr); random.shuffle(va); random.shuffle(te)
    def dump(lst,p):
        with p.open("w",encoding="utf-8") as f:
            for e in lst: f.write(json.dumps(e,ensure_ascii=False)+"\n")
    dump(tr, outdir/"train.jsonl"); dump(va, outdir/"val.jsonl"); dump(te, outdir/"test.jsonl")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir", default="data/spam")
    ap.add_argument("--total", type=int, default=DEF_TOTAL)
    ap.add_argument("--spam", type=float, default=DEF_SPAM)
    ap.add_argument("--zh", type=float, default=DEF_ZH)
    ap.add_argument("--len_short", type=float, default=DEF_LEN["short"])
    ap.add_argument("--len_medium", type=float, default=DEF_LEN["medium"])
    ap.add_argument("--len_long", type=float, default=DEF_LEN["long"])
    ap.add_argument("--multi", type=float, default=DEF_MULTI)
    ap.add_argument("--seed", type=int, default=DEF_SEED)
    args=ap.parse_args()
    len_ratio={"short":args.len_short,"medium":args.len_medium,"long":args.len_long}
    entries, stats = build(args.total, args.spam, args.zh, len_ratio, args.multi, args.seed)
    split_and_save(entries, Path(args.outdir))
    Path("reports_auto").mkdir(parents=True, exist_ok=True)
    Path("reports_auto/sma_data_stats.txt").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OUT] data/spam/{all,train,val,test}.jsonl")
    print("[STATS]", json.dumps(stats, ensure_ascii=False))

if __name__=="__main__":
    main()
