from __future__ import annotations
from typing import Any, Dict, List

# 規劃步驟（不做副作用）
PLAYBOOK: Dict[str, List[Dict[str, Any]]] = {
    "support": [
        {"id":"triage","action":"case.triage","params":{"severity":"auto"},"desc":"分級研判"},
        {"id":"create_ticket","action":"ticket.create","params":{"queue":"support"},"desc":"建立支援工單"},
        {"id":"kb_suggest","action":"kb.suggest","params":{"top_k":3},"desc":"建議知識庫文章"},
        {"id":"email_customer","action":"email.reply","params":{"template":"support_ack"},"desc":"寄出受理回覆"},
    ],
    "refund": [
        {"id":"collect_order_info","action":"gather","params":{"fields":["order_id","reason","amount"]},"desc":"收集退款必要資訊"},
        {"id":"create_ticket","action":"ticket.create","params":{"queue":"refunds"},"desc":"建立退款客服單"},
        {"id":"policy_check","action":"policy.check","params":{"policy":"refund"},"desc":"檢查退貨/退款政策"},
        {"id":"propose_refund","action":"finance.refund","params":{"mode":"original_payment"},"desc":"提出退款（規劃）"},
        {"id":"email_customer","action":"email.reply","params":{"template":"refund_ack"},"desc":"寄出退款受理信"},
    ],
    "biz_quote": [
        {"id":"qualify","action":"crm.qualify","params":{"model":"bant"},"desc":"商機資格（BANT）"},
        {"id":"prepare_quote","action":"pricing.prepare","params":{},"desc":"彙整需求並準備報價"},
        {"id":"book_meeting","action":"calendar.book","params":{"duration_min":30},"desc":"預約會議"},
        {"id":"pricing","action":"pricing.calc","params":{"tier":"auto"},"desc":"計算報價"},
        {"id":"generate_pdf","action":"doc.render","params":{"format":"pdf","template":"quote"},"desc":"產出 PDF 報價單"},
        {"id":"send_email","action":"email.reply","params":{"attach":"quote.pdf"},"desc":"寄出報價單"},
    ],
    "policy_qa": [
        {"id":"retrieve","action":"rag.retrieve","params":{"top_k":3},"desc":"檢索 FAQ 規則"},
        {"id":"compose","action":"rag.compose","params":{},"desc":"組合並回覆規則"},
    ],
    "complaint": [
        {"id":"auto_apology","action":"email.reply","params":{"template":"apology"},"desc":"自動道歉信"},
        {"id":"internal_alert","action":"alert","params":{"channel":"ops"},"desc":"內部告警"},
        {"id":"create_ticket","action":"ticket.create","params":{"queue":"complaints"},"desc":"建立投訴工單"},
    ],
    "profile_update": [
        {"id":"parse_old_new","action":"nlp.extract","params":{"fields":["phone","email","address","name"]},"desc":"解析新舊內容"},
        {"id":"diff_draft","action":"change.diff","params":{"draft":[]},"desc":"產出異動草稿"},
        {"id":"approval","action":"workflow.approval","params":{"level":"moderator"},"desc":"審批"},
        {"id":"update","action":"profile.update","params":{},"desc":"更新資料"},
        {"id":"email_customer","action":"email.reply","params":{"template":"profile_updated"},"desc":"通知更新完成"},
    ],
    "other": [
        {"id":"classify","action":"nlp.classify","params":{},"desc":"僅分類"},
        {"id":"summarize","action":"nlp.summarize","params":{},"desc":"摘要"},
        {"id":"no_op","action":"noop","params":{},"desc":"不觸發後續流程"},
    ],
}


# 發票
PLAYBOOK["invoice"] = [
    {"id":"reissue","action":"invoice.reissue","params":{},"desc":"重開發票"}
]
