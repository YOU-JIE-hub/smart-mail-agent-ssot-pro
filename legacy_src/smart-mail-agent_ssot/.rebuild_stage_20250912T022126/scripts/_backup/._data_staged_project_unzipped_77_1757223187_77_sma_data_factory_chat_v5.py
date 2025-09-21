#!/usr/bin/env python3
from __future__ import annotations
import json, random, re, hashlib, argparse
from pathlib import Path
from datetime import date
from collections import defaultdict

# ---------- helpers ----------
def ngrams(s,n=3): return [s[i:i+n] for i in range(max(0,len(s)-n+1))]
def normalize(s):
    s=s.lower(); s=re.sub(r'\s+',' ',s); s=re.sub(r'\d','#',s); s=re.sub(r'[^\w\u4e00-\u9fff]+',' ',s); return s.strip()
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

# ---------- lexicons ----------
EN_FIRST=["Alice","Bob","Charlie","David","Emily","Frank","Grace","Hannah","Ivan","Julia","Kevin","Laura","Michael","Nina","Oscar","Peter","Quinn","Robert","Sophie","Tom","Uma","Victor","Wendy","Xavier","Yvonne","Zack"]
EN_LAST =["Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Garcia","Wilson","Anderson","Taylor","Thomas","Moore","Martin","Lee","Thompson","White","Harris","Clark","Lewis","Walker","Young"]
CO=["acme","megacorp","globalcorp","contoso","citypower","ispnet","healthcare","utilityco","anycompany","techfirm","xyzinc","infotech","shopfast","smartcloud","telecomco","safebank","fintrust"]
HAM_DOM=[f"{c}.com" for c in CO]+["company.com","service.com","support.com","billing.com","hr.com","admin.com","it.com","sales.com","example.com","example.org","example.net","bank.com","cloud.com","corp.tw","corp.com.tw"]
SUSP_TLD=["zip","xyz","top","click","link","quest","gq","cf","ml","work","rest"]
PHISH_BASE=["account-sec","login-update","verify-now","reset-center","id-validate","customer-care","billing-alert","delivery-update","lottery-claim","wallet-update","auth-check","secure-id","safe-update","access-verify"]
SAFE_HOST=["portal","www","support","docs","secure","status"]
SAFE_PATH=["help","login","unsubscribe","status","pay","docs","kb","support","billing","dashboard"]

def ham_dom(): return random.choice(HAM_DOM)
def susp_url(): return f"http://{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789',k=8))}"
def safe_url(): return f"https://{random.choice(SAFE_HOST)}.{random.choice(CO)}.com/{random.choice(SAFE_PATH)}"
def invno(): return str(random.randint(10000,99999))
def trno():  return str(random.randint(10000,99999))
def tickno(): return f"#{random.randint(100000,999999)}"
def amt_usd(): return random.choice([49,59,75,99,120,250,400,500,799,1200])
def amt_ntd(): return random.choice([150,199,299,399,499,599,799,1200,1500,2500])
def blk_bulleted(lines): return "\n".join(random.choice(["- ","• "])+ln for ln in lines)
def blk_table(rows):   return "\n".join([f"{k}: {v}" for k,v in rows])
def blk_qna(pairs):    return "\n".join([f"Q: {q}\nA: {a}" for q,a in pairs])

def add_forward(body, lang):
    if lang=="en":
        hdr=f"----- Forwarded message -----\nFrom: Alice Smith <notice@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}>\nSubject: Update your details\nDate: 2025-08-10"
        tail=random.choice(["We noticed changes on your account.","Security check pending."])
    else:
        hdr=f"---------- 轉寄郵件 ----------\nFrom: 王小明 <notice@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}>\nSubject: 帳務異常通知\nDate: 2025-08-10"
        tail=random.choice(["請更新個人資料以維持服務。","安全檢查待完成。"])
    return body+"\n\n"+hdr+"\n"+tail
def add_reply(body, lang):
    return body+("\n\n----- Original Message -----\nI had an issue with my invoice last month." if lang=="en"
                 else "\n\n----- 原始郵件 -----\n上月帳單折扣未套用，請協助確認。")

# ---------- SPAM templates (always return) ----------
def spam_en_cred(lb, mp):
    v=random.randint(1,4)
    if v==1:
        subj="Unusual sign-in attempt"; body=f"Dear Customer,\nWe blocked a suspicious login.\nAction: verify at {susp_url()} within 24h.\nSecurity"
    elif v==2:
        subj="Account Security Alert"; body=blk_qna([("Why did I get this?","We detected unusual activity."),("What to do?","Verify your identity at the link.")])+f"\nLink: {susp_url()}"
    elif v==3:
        subj="Verify your account now – action needed"; body="Hello,\n"+blk_bulleted(["Identity check pending","Service will pause without verification"])+f"\nVerify: {susp_url()}\nRegards"
    else:
        subj="Your access is on hold"; body="Notice:\n"+blk_table([("Reason","Unconfirmed login"),("Deadline","24h"),("Resolution",susp_url())])
    if mp: body=add_forward(body,"en")
    return subj,body,[]

def spam_en_pay(lb, mp):
    subj="Payment verification needed"; v=random.randint(1,3)
    if v==1:
        body=f"Hello,\nYour recent payment could not be verified.\nConfirm here: {susp_url()}.\nAmount due: ${amt_usd()}.\nThank you."
    elif v==2:
        body="Billing Notice\n\n"+blk_table([("Status","Hold"),("Reason","Verification failed"),("Resolve",susp_url())])+"\nFinance"
    else:
        body="Dear user,\nWe could not match your billing details.\n"+blk_bulleted(["Card mismatch","Address requires update"])+f"\nProceed: {susp_url()}"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def spam_en_invoice(lb, mp):
    inv=invno(); ext=random.choice(["zip","js","htm"])
    subj=f"Invoice {inv} – payment required"; v=random.randint(1,3)
    if v==1:
        body="Dear Customer,\nPlease see attached invoice.\n"+blk_table([("Invoice",inv),("Status","Overdue")])+f"\n(Attachment: Invoice_{inv}.{ext})\nFinance"
    elif v==2:
        body=f"Reminder: invoice {inv} is overdue.\nOpen attachment to review terms.\nAttachment: Invoice_{inv}.{ext}"
    else:
        body=f"Payment overdue for invoice {inv}.\nDownload form: Invoice_{inv}.{ext}\nFinance Desk"
    if mp: body=add_forward(body,"en")
    return subj,body,[f"Invoice_{inv}.{ext}"]

def spam_en_delivery(lb, mp):
    tr=trno(); ext=random.choice(["zip","htm"])
    subj=f"Delivery failed – action required ({tr})"
    if random.random()<0.5:
        body=f"Dear Customer,\nPackage {tr} needs address confirmation.\nUpdate: {susp_url()} (48h)\nDelivery"
    else:
        body=blk_table([("Package",tr),("Status","Failed attempt"),("Next step",susp_url())])+"\n\nSupport Team"
    if mp: body=add_reply(body,"en")
    return subj,body,[f"Label_{tr}.{ext}"]

def spam_en_support_scam(lb, mp):
    subj="Remote support required for your PC"
    body="Hello,\nWe detected critical errors on your workstation.\n"+blk_bulleted(["License expired","Malware found"])+f"\nStart remote session: {susp_url()}"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def spam_en_prize(lb, mp):
    subj="FINAL NOTICE: Claim your prize"
    body="Congratulations!\nYour email won a cash prize.\nReply with full name and address to process.\nPromotions"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def spam_zh_cred(lb, mp):
    subj=random.choice(["重要：請立即驗證您的帳戶","安全提醒：異常登入"])
    v=random.randint(1,3)
    if v==1:
        body=f"親愛的用戶：\n偵測到異常活動，請於24小時內至 {susp_url()} 完成驗證。\n客服中心"
    elif v==2:
        body="提醒：\n"+blk_bulleted(["近期有異常登入跡象","需確認身份以維持服務"])+f"\n驗證連結：{susp_url()}"
    else:
        body=blk_table([("狀態","待驗證"),("期限","24 小時"),("連結",susp_url())])+"\n資訊安全組"
    if mp: body=add_forward(body,"zh")
    return subj,body,[]

def spam_zh_pay(lb, mp):
    subj="付款驗證失敗：請更新帳務資訊"
    if random.random()<0.5:
        body=f"您好：\n最近一次扣款未成功。請至 {susp_url()} 更新付款資料。\n本次應繳：NT${amt_ntd()}。\n感謝配合。"
    else:
        body="帳務通知：\n"+blk_table([("狀態","暫停"),("原因","驗證失敗"),("處理",susp_url())])+"\n財務部"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

def spam_zh_invoice(lb, mp):
    inv=invno(); ext=random.choice(["zip","js","htm"])
    subj=f"發票通知（{inv}）- 逾期未繳"
    if random.random()<0.5:
        body=f"尊敬的客戶：\n附件為本期發票（{inv}），目前顯示逾期，請儘速處理。\n（附件：{inv}.{ext}）\n財務部"
    else:
        body="催繳提醒：\n"+blk_table([("發票編號",inv),("狀態","逾期"),("付款","請參閱附件")])+f"\n附件：{inv}.{ext}"
    if mp: body=add_forward(body,"zh")
    return subj,body,[f"{inv}.{ext}"]

def spam_zh_delivery(lb, mp):
    tr=trno(); ext=random.choice(["zip","htm"])
    subj=f"【配送異常】包裹待處理（{tr}）"
    body=random.choice([f"您好：\n包裹（{tr}）因地址不全暫存本站，請於48小時內至 {susp_url()} 確認資訊並安排重新投遞。\n物流客服",
                        blk_table([("包裹",tr),("狀態","投遞失敗"),("下一步",susp_url())])+"\n客服中心"])
    if mp: body=add_reply(body,"zh")
    return subj,body,[f"通知單_{tr}.{ext}"]

def spam_zh_support_scam(lb, mp):
    subj="遠端協助：您的電腦偵測到嚴重錯誤"
    body="您好：\n系統發現多起錯誤與安全風險。\n"+blk_bulleted(["授權過期","疑似惡意程式"])+f"\n開始遠端支援：{susp_url()}"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

def spam_zh_prize(lb, mp):
    subj="恭喜中獎！請立即完成領取"
    body="您好：\n您在活動中獲得獎金，請回覆姓名與聯絡方式以便辦理。\n活動小組"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

# ---------- HAM templates (always return) ----------
def ham_en_invoice(lb, mp):
    inv=invno()
    subj=f"Invoice #{inv} for September"
    body=f"Hello,\nPlease find attached the invoice #{inv}. Total is ${amt_usd()}, payable by Oct 10, {date.today().year}.\nAccounts Receivable"
    if mp: body=add_reply(body,"en")
    return subj,body,[f"Invoice_{inv}.pdf"]

def ham_en_minutes(lb, mp):
    subj=f"Meeting Minutes – Project Update ({date.today().strftime('%Y-%m-%d')})"
    body="Hi Team,\n"+blk_bulleted(["Timeline adjusted","Risks reviewed","Next steps assigned"])+ "\nPlease see attached minutes.\nBest,\nPM"
    if mp: body=add_forward(body,"en")
    return subj,body,[f"MeetingMinutes_{date.today().strftime('%Y-%m-%d')}.docx"]

def ham_en_support(lb, mp):
    subj=f"RE: Support ticket {tickno()} resolved"
    body="Dear Customer,\nWe have resolved your issue and refreshed your account settings.\nIf anything else comes up, reply to this email.\nSupport Team"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def ham_en_announce(lb, mp):
    subj="Official Notice: System Maintenance"
    body="To all employees,\nWe will perform scheduled maintenance next Friday.\nPlease review the attached memo.\nIT Department"
    if mp: body=add_forward(body,"en")
    return subj,body,["Maintenance_Memo.pdf"]

def ham_en_marketing(lb, mp):
    subj=f"{random.choice(['September','October','Quarterly'])} Newsletter – Updates and Deals"
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
    subj=f"RE: 您的客服單 {tickno()} 已處理完成"
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

# ---------- build / split ----------
def bands64(x, bands=8, width=8): return [(x>>(i*width))&((1<<width)-1) for i in range(bands)]

def build(total=1000, spam_ratio=0.55, zh_ratio=0.50, multi_ratio=0.28, seed=1337):
    random.seed(seed)
    TARGET=total; SPAM_N=round(TARGET*spam_ratio)
    ZH_N=round(TARGET*zh_ratio); EN_N=TARGET-ZH_N
    lang_pool=["zh"]*ZH_N+["en"]*EN_N; random.shuffle(lang_pool)
    LEN_RATIO={"short":0.25,"medium":0.45,"long":0.30}
    len_pool=sum(([k]*round(TARGET*v) for k,v in LEN_RATIO.items()),[])
    while len(len_pool)>TARGET: len_pool.pop()
    while len(len_pool)<TARGET: len_pool.append("medium")
    random.shuffle(len_pool)
    mpara=[True]*round(TARGET*multi_ratio)+[False]*(TARGET-round(TARGET*multi_ratio)); random.shuffle(mpara)

    entries=[]; exact=set(); feats=[]; buckets={i:{} for i in range(8)}
    sid=1; hid=1

    def uniq_ok(subj, body):
        norm=normalize(subj+"\n"+body); key=hashlib.sha256(norm.encode('utf-8')).hexdigest()
        if key in exact: return False
        grams=ngrams(norm,3); sh=simhash(grams) if grams else 0
        cands=set(); b=bands64(sh)
        for i,bi in enumerate(b):
            lst=buckets[i].get(bi)
            if lst: cands.update(lst)
        for idx in cands:
            n2,g2,sh2=feats[idx]
            if (hamming(sh,sh2)<=4 and jaccard(grams,g2)>=0.87) or jaccard(grams,g2)>=0.95:
                return False
        exact.add(key); idx=len(feats); feats.append((norm,grams,sh))
        for i,bi in enumerate(b): buckets[i].setdefault(bi, []).append(idx)
        return True

    attempts=0
    while len(entries)<TARGET and attempts<TARGET*600:
        attempts+=1
        label="spam" if len(entries)<SPAM_N else "ham"
        i=len(entries); lang=lang_pool[i]; lb=len_pool[i]; mp=mpara[i]
        if label=="spam" and lang=="en":
            gen={"cred":spam_en_cred,"pay":spam_en_pay,"inv":spam_en_invoice,"del":spam_en_delivery,"rsup":spam_en_support_scam,"prize":spam_en_prize}
        elif label=="spam":
            gen={"cred":spam_zh_cred,"pay":spam_zh_pay,"inv":spam_zh_invoice,"del":spam_zh_delivery,"rsup":spam_zh_support_scam,"prize":spam_zh_prize}
        elif lang=="en":
            gen={"inv":ham_en_invoice,"min":ham_en_minutes,"sup":ham_en_support,"ann":ham_en_announce,"mkt":ham_en_marketing}
        else:
            gen={"inv":ham_zh_invoice,"min":ham_zh_minutes,"sup":ham_zh_support,"ann":ham_zh_announce,"mkt":ham_zh_marketing}

        subtype=random.choice(list(gen.keys()))
        subj, body, att = gen[subtype](lb, mp)

        frm = (f"no-reply@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}"
               if label=="spam" else f"{random.choice(['billing','support','hr','admin','it','service','news'])}@{ham_dom()}")

        # length padding
        def words(x): return max(1, len(re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]+',' ',x).split()))
        target_min={"short":15,"medium":41,"long":121}[lb]
        fillers_en=["Please review and respond.","This is an automated notice.","Please keep this email for your records."]
        fillers_zh=["若有疑問請回覆此信。","此為系統自動通知。","請留存此郵件備查。","如需協助請洽客服。"]
        fillers = fillers_en if lang=="en" else fillers_zh
        while words(subj+" "+body) < target_min: body += "\n"+random.choice(fillers)

        if not uniq_ok(subj, body): continue
        _id=("S"+f"{sid:06d}") if label=="spam" else ("H"+f"{hid:06d}")
        if label=="spam": sid+=1
        else: hid+=1
        entries.append({"id":_id,"subject":subj,"body":body,"from":frm,"attachments":att,"label":label})

    if len(entries)<TARGET: raise RuntimeError(f"only {len(entries)}/{TARGET} unique; try --seed")
    return entries

def split_and_save(entries, outdir:Path, seed=42):
    random.seed(seed); outdir.mkdir(parents=True, exist_ok=True)
    # save 3 files (train/val/test)
    def lang_detect(e): return "zh" if re.search(r'[\u4e00-\u9fff]', e["subject"]+" "+e["body"]) else "en"
    buckets=defaultdict(list)
    for e in entries: buckets[(e["label"],lang_detect(e))].append(e)
    train=[]; val=[]; test=[]
    for _,lst in buckets.items():
        random.shuffle(lst)
        n=len(lst); ntr=int(n*0.80); nva=int(n*0.10); nte=n-ntr-nva
        train+=lst[:ntr]; val+=lst[ntr:ntr+nva]; test+=lst[ntr+nva:]
    for name,lst in [("train",train),("val",val),("test",test)]:
        with (outdir/f"{name}.jsonl").open("w",encoding="utf-8") as f:
            for e in lst: f.write(json.dumps(e, ensure_ascii=False)+"\n")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir", default="data/spam")
    ap.add_argument("--total", type=int, default=1000)
    ap.add_argument("--spam", type=float, default=0.55)
    ap.add_argument("--zh",   type=float, default=0.50)
    ap.add_argument("--multi", type=float, default=0.28)
    ap.add_argument("--seed",  type=int, default=1337)
    a=ap.parse_args()
    entries=build(total=a.total, spam_ratio=a.spam, zh_ratio=a.zh, multi_ratio=a.multi, seed=a.seed)
    split_and_save(entries, Path(a.outdir))

if __name__=="__main__":
    main()
