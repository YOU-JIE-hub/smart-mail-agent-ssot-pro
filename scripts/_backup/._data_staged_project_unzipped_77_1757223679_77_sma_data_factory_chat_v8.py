#!/usr/bin/env python3
from __future__ import annotations
import json, random, re, hashlib, argparse
from pathlib import Path
from datetime import date
from collections import defaultdict

# ---------- helpers ----------
def ngrams(s,n=3): return [s[i:i+n] for i in range(max(0,len(s)-n+1))]
def normalize(s):
    import unicodedata as U
    s=U.normalize("NFKC", s.lower())
    s=re.sub(r'\s+',' ',s); s=re.sub(r'\d','#',s); s=re.sub(r'[^\w\u4e00-\u9fff]+',' ',s)
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
    A=set(a); B=set(b); 
    return 0.0 if not A or not B else len(A&B)/len(A|B)
def bands64(x, bands=8, width=8): return [(x>>(i*width))&((1<<width)-1) for i in range(bands)]
def words(x): return max(1, len(re.sub(r'[^A-Za-z0-9\u4e00-\u9fff]+',' ',x).split()))

# ---------- lexicons ----------
CO=["acme","megacorp","globalcorp","contoso","citypower","ispnet","healthcare","utilityco","anycompany","techfirm","xyzinc","infotech","shopfast","smartcloud","telecomco","safebank","fintrust"]
HAM_DOM=[f"{c}.com" for c in CO]+["company.com","service.com","support.com","billing.com","hr.com","admin.com","it.com","sales.com","example.com","example.org","example.net","bank.com","cloud.com","corp.tw","corp.com.tw"]
SUSP_TLD=["zip","xyz","top","click","link","quest","gq","cf","ml","work","rest"]
PHISH_BASE=["account-sec","login-update","verify-now","reset-center","id-validate","customer-care","billing-alert","delivery-update","lottery-claim","wallet-update","auth-check","secure-id","safe-update","access-verify"]
SAFE_HOST=["portal","www","support","docs","secure","status"]
SAFE_PATH=["help","login","unsubscribe","status","pay","docs","kb","support","billing","dashboard"]
BRANDS=["paypal","apple","google","microsoft","amazon","netflix","facebook","bank","office365","dropbox"]

EN_KW = re.compile(r'\b(verify|login|security|suspend|reset|update|billing|invoice|delivery|remote|support|prize|lottery)\b', re.I)
ZH_KW = re.compile(r'(驗證|登錄|登入|安全|暫停|重設|更新|帳務|發票|配送|遠端|支援|中獎|獎金)')

def ham_dom(): return random.choice(HAM_DOM)
def invno(): return str(random.randint(10000,99999))
def trno(): return str(random.randint(10000,99999))
def tickno(): return f"#{random.randint(100000,999999)}"
def amt_usd(): return random.choice([49,59,75,99,120,250,400,500,799,1200])
def amt_ntd(): return random.choice([150,199,299,399,499,599,799,1200,1500,2500])
def blk_bulleted(lines): return "\n".join(random.choice(["- ","• "])+ln for ln in lines)
def blk_table(rows): return "\n".join([f"{k}: {v}" for k,v in rows])
def blk_qna(pairs): return "\n".join([f"Q: {q}\nA: {a}" for q,a in pairs])
def to_fullwidth_digits(s):
    def f(c): 
        return chr(ord('０')+(ord(c)-ord('0'))) if '0'<=c<='9' else c
    return ''.join(f(c) for c in s)
def insert_zwj(s):
    ZW="\u200b"
    if len(s)<4: return s
    pos=sorted(random.sample(range(1,len(s)-1), k=min(2,max(1,len(s)//10))))
    out=list(s)
    for i,p in enumerate(pos): out.insert(p+i, ZW)
    return ''.join(out)
def homograph(s):
    s=re.sub(r'rn','m',s)
    if random.random()<0.3: s=s.replace('l','1')
    if random.random()<0.3: s=s.replace('O','0')
    return s
def susp_url(): 
    return f"http://{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789',k=8))}"
def brand_lookalike():
    b=random.choice(BRANDS)
    d=random.choice([
        f"{b}.com.{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}",
        f"login.{b}-secure.{random.choice(SUSP_TLD)}",
        f"{b}-auth.{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}",
        f"secure-{b}.verify.{random.choice(SUSP_TLD)}",
    ])
    return "http://"+homograph(d)+"/"+''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789',k=6))
def safe_url(): return f"https://{random.choice(SAFE_HOST)}.{random.choice(CO)}.com/{random.choice(SAFE_PATH)}"

def add_forward(body, lang, depth=None):
    if depth is None: depth=random.choice([1,2,3])
    for _ in range(depth):
        if lang=="en":
            hdr=f"----- Forwarded message -----\nFrom: Alice Smith <notice@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}>\nSubject: Update your details\nDate: 2025-08-10"
            tail=random.choice(["We noticed changes on your account.","Security check pending."])
        else:
            hdr=f"---------- 轉寄郵件 ----------\nFrom: 王小明 <notice@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}>\nSubject: 帳務異常通知\nDate: 2025-08-10"
            tail=random.choice(["請更新個人資料以維持服務。","安全檢查待完成。"])
        body=body+"\n\n"+hdr+"\n"+tail
    return body
def add_reply(body, lang, depth=None):
    if depth is None: depth=random.choice([1,2])
    for _ in range(depth):
        body += ("\n\n----- Original Message -----\nI had an issue with my invoice last month."
                 if lang=="en" else "\n\n----- 原始郵件 -----\n上月帳單折扣未套用，請協助確認。")
    return body

# ---------- spam templates ----------
def spam_en_cred(lb, mp):
    v=random.randint(1,4)
    if v==1: subj="Unusual sign-in attempt"; body=f"Dear Customer,\nWe blocked a suspicious login.\nAction: verify at {susp_url()} within 24h.\nSecurity"
    elif v==2: subj="Account Security Alert"; body=blk_qna([("Why did I get this?","We detected unusual activity."),("What to do?","Verify your identity at the link.")])+f"\nLink: {random.choice([susp_url(), brand_lookalike()])}"
    elif v==3: subj="Verify your account now – action needed"; body="Hello,\n"+blk_bulleted(["Identity check pending","Service will pause without verification"])+f"\nVerify: {random.choice([susp_url(), brand_lookalike()])}\nRegards"
    else: subj="Your access is on hold"; body="Notice:\n"+blk_table([("Reason","Unconfirmed login"),("Deadline","24h"),("Resolution",random.choice([susp_url(), brand_lookalike()]))])
    if mp: body=add_forward(body,"en")
    return subj,body,[]

def spam_en_pay(lb, mp):
    subj="Payment verification needed"; v=random.randint(1,3)
    if v==1: body=f"Hello,\nYour recent payment could not be verified.\nConfirm: {random.choice([susp_url(), brand_lookalike()])}.\nAmount due: ${amt_usd()}."
    elif v==2: body="Billing Notice\n\n"+blk_table([("Status","Hold"),("Reason","Verification failed"),("Resolve",random.choice([susp_url(), brand_lookalike()]))])+"\nFinance"
    else: body="Dear user,\nWe could not match your billing details.\n"+blk_bulleted(["Card mismatch","Address requires update"])+f"\nProceed: {random.choice([susp_url(), brand_lookalike()])}"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def spam_en_invoice(lb, mp):
    inv=invno(); ext=random.choice(["zip","js","htm"]); subj=f"Invoice {inv} – payment required"
    v=random.randint(1,3)
    if v==1: body="Dear Customer,\nPlease see attached invoice.\n"+blk_table([("Invoice",inv),("Status","Overdue")])+f"\nAttachment: Invoice_{inv}.{ext}"
    elif v==2: body=f"Reminder: invoice {inv} is overdue.\nOpen attachment to review terms.\nAttachment: Invoice_{inv}.{ext}"
    else: body=f"Payment overdue for invoice {inv}.\nDownload form: Invoice_{inv}.{ext}\nFinance Desk"
    if mp: body=add_forward(body,"en")
    return subj,body,[f"Invoice_{inv}.{ext}"]

def spam_en_delivery(lb, mp):
    tr=trno(); ext=random.choice(["zip","htm"]); subj=f"Delivery failed – action required ({tr})"
    body=random.choice([f"Dear Customer,\nPackage {tr} needs address confirmation.\nUpdate: {random.choice([susp_url(), brand_lookalike()])} (48h)\nDelivery",
                        blk_table([("Package",tr),("Status","Failed attempt"),("Next step",random.choice([susp_url(), brand_lookalike()]))])+"\n\nSupport Team"])
    if mp: body=add_reply(body,"en")
    return subj,body,[f"Label_{tr}.{ext}"]

def spam_en_support_scam(lb, mp):
    subj="Remote support required for your PC"
    body="Hello,\nWe detected critical errors on your workstation.\n"+blk_bulleted(["License expired","Malware found"])+f"\nStart remote session: {random.choice([susp_url(), brand_lookalike()])}"
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
    if v==1: body=f"親愛的用戶：\n偵測到異常活動，請於24小時內至 {random.choice([susp_url(), brand_lookalike()])} 完成驗證。\n客服中心"
    elif v==2: body="提醒：\n"+blk_bulleted(["近期有異常登入跡象","需確認身份以維持服務"])+f"\n驗證連結：{random.choice([susp_url(), brand_lookalike()])}"
    else: body=blk_table([("狀態","待驗證"),("期限","24 小時"),("連結",random.choice([susp_url(), brand_lookalike()]))])+"\n資訊安全組"
    if mp: body=add_forward(body,"zh")
    return subj,body,[]

def spam_zh_pay(lb, mp):
    subj="付款驗證失敗：請更新帳務資訊"
    if random.random()<0.5: body=f"您好：\n最近一次扣款未成功。請至 {random.choice([susp_url(), brand_lookalike()])} 更新付款資料。\n本次應繳：NT${amt_ntd()}。"
    else: body="帳務通知：\n"+blk_table([("狀態","暫停"),("原因","驗證失敗"),("處理",random.choice([susp_url(), brand_lookalike()]))])+"\n財務部"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

def spam_zh_invoice(lb, mp):
    inv=invno(); ext=random.choice(["zip","js","htm"]); subj=f"發票通知（{inv}）- 逾期未繳"
    if random.random()<0.5: body=f"尊敬的客戶：\n附件為本期發票（{inv}），目前顯示逾期，請儘速處理。\n附件：{inv}.{ext}"
    else: body="催繳提醒：\n"+blk_table([("發票編號",inv),("狀態","逾期"),("付款","請參閱附件")])+f"\n附件：{inv}.{ext}"
    if mp: body=add_forward(body,"zh")
    return subj,body,[f"{inv}.{ext}"]

def spam_zh_delivery(lb, mp):
    tr=trno(); ext=random.choice(["zip","htm"]); subj=f"【配送異常】包裹待處理（{tr}）"
    body=random.choice([f"您好：\n包裹（{tr}）因地址不全暫存本站，請於48小時內至 {random.choice([susp_url(), brand_lookalike()])} 確認資訊並安排重新投遞。\n物流客服",
                        blk_table([("包裹",tr),("狀態","投遞失敗"),("下一步",random.choice([susp_url(), brand_lookalike()]))])+"\n客服中心"])
    if mp: body=add_reply(body,"zh")
    return subj,body,[f"通知單_{tr}.{ext}"]

def spam_zh_support_scam(lb, mp):
    subj="遠端協助：您的電腦偵測到嚴重錯誤"
    body="您好：\n系統發現多起錯誤與安全風險。\n"+blk_bulleted(["授權過期","疑似惡意程式"])+f"\n開始遠端支援：{random.choice([susp_url(), brand_lookalike()])}"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

def spam_zh_prize(lb, mp):
    subj="恭喜中獎！請立即完成領取"
    body="您好：\n您在活動中獲得獎金，請回覆姓名與聯絡方式以便辦理。\n活動小組"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

# ---------- ham templates（多做安全場景 + 難例） ----------
def ham_en_invoice(lb, mp):
    inv=invno(); subj=f"Invoice #{inv} for September"
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

def ham_en_security_notice(lb, mp):  # 帶關鍵詞但安全鏈結
    subj="Security update notice – informational only"
    body="Heads up:\nWe will rotate SSO certificates next week.\nPlease review details at "+safe_url()+"\nNo action is required."
    if mp: body=add_forward(body,"en")
    return subj,body,[]

def ham_en_timesheet(lb, mp):  # 帶 login/verify 字眼但內部 portal
    subj="Please verify your timesheet by Friday"
    body="Hi,\nLog in to the internal portal to verify your hours: "+safe_url()+"\nThanks."
    return subj,body,[]

def ham_en_marketing(lb, mp):
    subj=f"{random.choice(['September','October','Quarterly'])} Newsletter – Updates and Deals"
    body="Dear Customer,\nThis month's updates and offers:\n"+blk_bulleted(["New arrivals","Top picks","15% off with code"])+f"\nUnsubscribe: {safe_url()}"
    if mp: body=add_reply(body,"en")
    return subj,body,[]

def ham_zh_invoice(lb, mp):
    inv=invno(); subj=f"繳費通知：發票 {inv}"
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

def ham_zh_security_notice(lb, mp):
    subj="資訊安全通知（僅供參考）"
    body="說明：下週將更新 SSO 憑證，詳情請見 "+safe_url()+"。本通知無需操作。"
    return subj,body,[]

def ham_zh_marketing(lb, mp):
    subj="本月電子報｜優惠與新品"
    body=f"親愛的用戶：\n本期精選內容與優惠請見內文。如欲退訂：{safe_url()}\n行銷小組"
    if mp: body=add_reply(body,"zh")
    return subj,body,[]

SPAM_EN={"cred":spam_en_cred,"pay":spam_en_pay,"inv":spam_en_invoice,"del":spam_en_delivery,"rsup":spam_en_support_scam,"prize":spam_en_prize}
SPAM_ZH={"cred":spam_zh_cred,"pay":spam_zh_pay,"inv":spam_zh_invoice,"del":spam_zh_delivery,"rsup":spam_zh_support_scam,"prize":spam_zh_prize}
HAM_EN ={"inv":ham_en_invoice,"min":ham_en_minutes,"sup":ham_en_support,"sec":ham_en_security_notice,"time":ham_en_timesheet,"mkt":ham_en_marketing}
HAM_ZH ={"inv":ham_zh_invoice,"min":ham_zh_minutes,"sup":ham_zh_support,"sec":ham_zh_security_notice,"mkt":ham_zh_marketing}

# ---------- signal guards ----------
SUS_ATT=('.zip','.js','.htm','.html')
def count_spam_signals(lang, subj, body, att):
    bad_link = bool(re.search(r'http://[^ \n]+\.(%s)\b' % "|".join(SUSP_TLD), body))
    lookalike = bool(re.search(r'http://(?:[^/\s]+\.)?(?:%s)[^/\s]*\.(?:%s)\b' % ("|".join(BRANDS), "|".join(SUSP_TLD)), body))
    sus_att = any(a.lower().endswith(SUS_ATT) for a in att)
    kw = bool((EN_KW.search(subj+" "+body)) if lang=="en" else (ZH_KW.search(subj+" "+body)))
    return int(bad_link)+int(lookalike)+int(sus_att)+int(kw)

def ensure_spam_min_signals(lang, subj, body, att, need=2):
    # 盡量以最小改動補足訊號
    while count_spam_signals(lang, subj, body, att) < need:
        if random.random()<0.5:
            body += ("\nVerify now: "+random.choice([susp_url(), brand_lookalike()])) if lang=="en" else ("\n請立刻驗證： "+random.choice([susp_url(), brand_lookalike()]))
        else:
            att = list(att)+[random.choice([f"Invoice_{invno()}.zip", f"Form_{invno()}.js", f"Doc_{invno()}.htm"])]
    return subj, body, att

def clean_ham(lang, subj, body, att, strict=True):
    # 移除 http:// 連結，保留少量 https:// 安全連結；替換易誤殺關鍵詞；附件限 pdf/docx
    if strict:
        body = re.sub(r'http://\S+','', body)
        subj = re.sub(r'http://\S+','', subj)
        # 替換詞
        if lang=="en":
            body=re.sub(r'\bverify\b','confirm',body,flags=re.I)
            subj=re.sub(r'\bverify\b','confirm',subj,flags=re.I)
            body=re.sub(r'\bsecurity\b','information',body,flags=re.I)
        else:
            body=re.sub(r'(驗證|登入|登錄)','確認',body)
            subj=re.sub(r'(驗證|登入|登錄)','確認',subj)
        # 附件白名單
        att=[a for a in att if a.lower().endswith(('.pdf','.docx'))]
    return subj, body, att

# ---------- generator ----------
def build(total=1000, spam_ratio=0.55, zh_ratio=0.50, multi_ratio=0.28, seed=1337, strict_ham=True, min_spam_signals=2):
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
    while len(entries)<TARGET and attempts<TARGET*2000:
        attempts+=1
        label="spam" if len(entries)<SPAM_N else "ham"
        i=len(entries); lang=lang_pool[i]; lb=len_pool[i]; mp=mpara[i]
        gen = SPAM_EN if (label=="spam" and lang=="en") else SPAM_ZH if label=="spam" else HAM_EN if lang=="en" else HAM_ZH
        subtype=random.choice(list(gen.keys()))
        subj, body, att = gen[subtype](lb, mp)

        # 強化/清理
        if label=="spam":
            subj, body, att = ensure_spam_min_signals(lang, subj, body, att, need=min_spam_signals)
        else:
            subj, body, att = clean_ham(lang, subj, body, att, strict=strict_ham)

        # 轉寄/回覆增量 & 混淆
        if random.random()<0.15: body=add_forward(body,lang,depth=random.choice([2,3]))
        if random.random()<0.15: body=add_reply(body,lang,depth=random.choice([2,3]))
        if random.random()<0.30:
            subj, body = insert_zwj(subj), insert_zwj(body)
        if random.random()<0.20:
            subj, body = to_fullwidth_digits(subj), to_fullwidth_digits(body)

        frm = (f"no-reply@{random.choice(PHISH_BASE)}.{random.choice(SUSP_TLD)}"
               if label=="spam" else f"{random.choice(['billing','support','hr','admin','it','service','news'])}@{ham_dom()}")

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
    # save all
    with (outdir/"all.jsonl").open("w",encoding="utf-8") as f:
        for e in entries: f.write(json.dumps(e, ensure_ascii=False)+"\n")
    # stratified 80/10/10 by label+lang
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
    ap.add_argument("--seed",  type=int, default=20250830)
    ap.add_argument("--strict", type=int, default=1)  # 1=嚴格 ham
    ap.add_argument("--min_spam_signals", type=int, default=2)
    a=ap.parse_args()
    es=build(total=a.total, spam_ratio=a.spam, zh_ratio=a.zh, multi_ratio=a.multi,
             seed=a.seed, strict_ham=bool(a.strict), min_spam_signals=a.min_spam_signals)
    split_and_save(es, Path(a.outdir))

if __name__=="__main__":
    main()
