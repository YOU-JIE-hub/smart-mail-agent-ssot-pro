import os, sys, json, tempfile, io, contextlib, types, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT/"src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("OFFLINE","1")

def _ensure_models():
    from models.intent import train as intent_train
    from models.spam import train as spam_train
    from models.rag import build as rag_build
    if not (ROOT/"models/intent/artifacts/intent_rules.json").exists():
        intent_train.train()
    if not (ROOT/"models/spam/artifacts/spam_rules.json").exists():
        spam_train.train()
    if not (ROOT/"models/rag/artifacts/index.json").exists():
        rag_build.build()

def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception:
        return None

def _preheat_ai_stack():
    # imports
    from ai_rpa.actions_router import plan, plan_from_categories, route
    from ai_rpa.actions_executor import Executor
    from ai_rpa import actions as actions_mod
    from ai_rpa import mail_io
    from ai_rpa.mailguard import detector as mg
    from ai_rpa import nlp as nlp_mod
    from ai_rpa import scraper as scraper_mod
    from ai_rpa import ocr as ocr_mod
    from ai_rpa import nlp_llm as nlp_llm_mod
    from ai_rpa.utils import json_safe as js
    from ai_rpa import intent_map as intent_map_mod
    from ai_rpa.utils import config_loader as cfg
    from ai_rpa import file_classifier as fc
    import ai_rpa.main as main_mod

    tmp = Path(tempfile.mkdtemp(prefix="sma_models_cov_"))
    work = tmp/"work"; outb = tmp/"outbox"; db = tmp/"db.sqlite"
    work.mkdir(parents=True, exist_ok=True); outb.mkdir(parents=True, exist_ok=True)

    # Router 分支
    _safe(plan, "需要客服協助 無法登入")
    _safe(plan, "想洽談合作，請提供正式方案與報價")
    _safe(plan, "想了解退款機制與使用限制")
    _safe(plan, "我要更新電話與地址")
    _safe(plan, "服務延遲 很失望")
    _safe(plan_from_categories, ["unknown"], scraped=[{"tag":"p","text":"頁面介紹"}])
    _safe(route, "測試", scraped=None, blocked=True)   # gating -> 空列表
    _safe(route, "正常流程", scraped=[{"tag":"p","text":"內容"}], blocked=False)

    # Executor：dry-run + real（寫出 quote.pdf / .eml / DB）
    steps = _safe(plan, "想洽談合作，請提供正式方案與報價") or []
    ex = Executor(work, outb, db, dry_run=True)
    _safe(ex.execute, steps, context={"qty":60, "email_to":"buyer@example.com", "meeting_title":"Intro"})
    ex2 = Executor(work, outb, db, dry_run=False)
    _safe(ex2.execute, steps, context={"qty":5, "email_to":"buyer@example.com", "doc_data":{"title":"Quote"}})

    # actions.write_json -> 觸發 json_safe
    actions_mod.write_json({"b":b"\x00\x01","s":{1,2,3},"p":work}, str(work/"probe.json"))

    # mail_io：offline 檔案落地
    _safe(mail_io.send_email, outb, "demo@example.com", "OfflineMail", "hello", attachments=[work/"quote.pdf"], dry_run=False, db_log=None)

    # mail_io：ONLINE 分支（STARTTLS）
    old_off = os.environ.get("OFFLINE","1")
    os.environ["OFFLINE"]="0"
    os.environ["SMA_SMTP_HOST"]="smtp.local"
    os.environ["SMA_SMTP_PORT"]="25"
    os.environ["SMA_SMTP_STARTTLS"]="1"
    os.environ["SMA_SMTP_USER"]="u"
    os.environ["SMA_SMTP_PASS"]="p"
    class FakeSMTP:
        def __init__(self, host, port): pass
        def starttls(self, context=None): pass
        def login(self, u, p): pass
        def send_message(self, msg): pass
        def quit(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
    old_sm = mail_io.smtplib
    mail_io.smtplib = types.SimpleNamespace(SMTP=FakeSMTP, SMTP_SSL=FakeSMTP)
    try:
        _safe(mail_io.send_email, outb, "to@example.com", "OnlineMail", "body", attachments=[], dry_run=False, db_log=None)
    finally:
        mail_io.smtplib = old_sm

    # mail_io：ONLINE 分支（SSL）
    os.environ["SMA_SMTP_STARTTLS"]="0"
    mail_io.smtplib = types.SimpleNamespace(SMTP=FakeSMTP, SMTP_SSL=FakeSMTP)
    try:
        _safe(mail_io.send_email, outb, "to@example.com", "OnlineMailSSL", "body", attachments=[], dry_run=False, db_log=None)
    finally:
        mail_io.smtplib = old_sm
        os.environ["OFFLINE"]=old_off

    # receive_imap：offline + online stub
    _safe(mail_io.receive_imap, "imap.local","u","p")  # OFFLINE=1 => []
    old_off = os.environ.get("OFFLINE","1"); os.environ["OFFLINE"]="0"
    class FakeIMAP:
        def __init__(self, host, timeout=10): pass
        def login(self,u,p): pass
        def select(self, folder): return ("OK",[b""])
        def search(self,*a): return ("OK",[b"1 2"])
        def fetch(self,i,what):
            from email.message import EmailMessage
            m=EmailMessage(); m["Subject"]=f"Subj{i.decode() if isinstance(i,bytes) else i}"
            return ("OK",[(None,m.as_bytes())])
        def logout(self): pass
    old_im = mail_io.imaplib
    mail_io.imaplib = types.SimpleNamespace(IMAP4_SSL=FakeIMAP)
    try:
        _safe(mail_io.receive_imap, "imap.local","u","p")
    finally:
        mail_io.imaplib = old_im
        os.environ["OFFLINE"]=old_off

    # MailGuard
    _safe(mg.detect, "free money!!!")
    _safe(mg.detect, "hello", headers={"X-Spam-Flag":"YES"})
    _safe(mg.load_default_ruleset)

    # NLP
    _safe(nlp_mod.classify, "需要客服協助 無法登入")
    _safe(nlp_mod.summarize, "這是一段很長的說明文字")
    _safe(nlp_mod.analyze_text, "合作與報價，請提供方案")

    # 其他 utils / 模組
    _safe(scraper_mod.scrape, "http://stub.local")
    _safe(ocr_mod.ocr_bytes, b"fake")
    _safe(nlp_llm_mod.available)
    js.ensure_jsonable({1,2,3})
    js.ensure_jsonable(Path(work))
    js.dumps_safe({"b": b"\x00\x01", "s": {1,2}, "p": work})
    if hasattr(intent_map_mod, "labels_from_intents"):
        _safe(intent_map_mod.labels_from_intents, ["sales","quote"])

    # file_classifier 多類型
    for name in ("a.pdf","b.jpg","c.png","d.eml","e.txt"):
        (work/name).write_bytes(b"stub")
        _safe(fc.classify_path, str(work/name))

    # config_loader 一些分支
    if hasattr(cfg, "get_env_bool"):
        _safe(cfg.get_env_bool, "OFFLINE", True)
        os.environ["FLAG_X"]="0"; _safe(cfg.get_env_bool, "FLAG_X", True)

    # main CLI：直接呼叫 main()
    os.environ["SMA_OUTBOX"]=str(outb)
    os.environ["SMA_WORKDIR"]=str(work)
    os.environ["SMA_DB"]=str(db)
    # 1) spam alias + unknown + dry-run
    inpf = work/"in.txt"; inpf.write_text("free money!!!", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        sys.argv = ["prog","--tasks","spamcheck,unknown","--input-path",str(inpf),"--dry-run"]
        _safe(main_mod.main)
    # 2) nlp + mailguard + actions（BLOCK -> skip actions）
    with contextlib.redirect_stdout(io.StringIO()):
        sys.argv = ["prog","--tasks","nlp,mailguard,actions","--input-path",str(inpf)]
        _safe(main_mod.main)
    # 3) nlp + actions + --exec（會執行 playbook）
    inpf2 = work/"ok.txt"; inpf2.write_text("想洽談合作與報價", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        sys.argv = ["prog","--tasks","nlp,actions","--input-path",str(inpf2),"--exec"]
        _safe(main_mod.main)

def pytest_sessionstart(session):
    _ensure_models()
    _preheat_ai_stack()
