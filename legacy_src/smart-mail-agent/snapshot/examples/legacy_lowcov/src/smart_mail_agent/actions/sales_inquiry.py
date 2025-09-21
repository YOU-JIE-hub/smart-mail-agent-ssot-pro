from __future__ import annotations

import json

#!/usr/bin/env python3
# 檔案位置：src/actions/sales_inquiry.py
# 模組用途：處理商務詢問；抽取關鍵欄位並以模板產出需求彙整 .md 附件；補充 meta.next_step
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:
    Environment = None  # type: ignore

ACTION_NAME = "sales_inquiry"


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _load_template_env() -> Environment | None:
    """
    嘗試從 templates/ 與 src/templates/ 建立 Jinja2 環境
    """
    if Environment is None:
        return None
    search_paths: list[str] = []
    for d in ("templates", "src/templates"):
        if Path(d).is_dir():
            search_paths.append(d)
    if not search_paths:
        return None
    return Environment(
        loader=FileSystemLoader(search_paths),
        autoescape=select_autoescape(enabled_extensions=("j2", "html", "md")),
        enable_async=False,
    )


# 規則式抽取：公司、數量、截止、預算、關鍵詞
RE_COMPANY = re.compile(
    r"([A-Za-z\u4e00-\u9fa5][\w\u4e00-\u9fa5＆&\.-]{1,30})(?:股份有限公司|有限公司|公司)", re.I
)
RE_QUANTITY = re.compile(r"(\d{1,6})\s*(台|件|個|套|pcs?)", re.I)
RE_BUDGET = re.compile(r"(?:NTD?|新台幣|\$)\s*([0-9][0-9,]{0,12})(?:\s*(萬|千|元|dollars?))?", re.I)
RE_DATE1 = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")  # YYYY-MM-DD
RE_DATE2 = re.compile(r"(\d{1,2})[月/](\d{1,2})[日]?", re.I)  # M月D日 or M/D
RE_KEYWORDS = re.compile(r"[A-Za-z\u4e00-\u9fa5]{2,15}")

COMMON_STOP = {
    "我們",
    "你好",
    "您好",
    "謝謝",
    "請問",
    "協助",
    "需要",
    "希望",
    "聯繫",
    "安排",
    "報價",
    "需求",
    "規格",
    "提供",
}


def _extract_fields(subject: str, body: str, sender: str | None) -> dict[str, Any]:
    text = f"{subject}\n{body}"
    company = None
    m = RE_COMPANY.search(text)
    if m:
        company = m.group(0)

    quantity = None
    m = RE_QUANTITY.search(text)
    if m:
        quantity = f"{m.group(1)}{m.group(2)}"

    budget = None
    m = RE_BUDGET.search(text)
    if m:
        money = m.group(1).replace(",", "")
        unit = m.group(2) or "元"
        budget = f"{money}{unit}"

    deadline = None
    m = RE_DATE1.search(text)
    if m:
        yyyy, mm, dd = m.groups()
        deadline = f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    else:
        m = RE_DATE2.search(text)
        if m:
            # 以當年補齊
            year = datetime.now().year
            mm, dd = m.groups()
            deadline = f"{year}-{int(mm):02d}-{int(dd):02d}"

    kw_raw = [w for w in RE_KEYWORDS.findall(text) if w not in COMMON_STOP]
    keywords = []
    seen = set()
    for w in kw_raw:
        if w.lower() in seen:
            continue
        seen.add(w.lower())
        keywords.append(w)
        if len(keywords) >= 8:
            break

    contact = None
    if sender and "@" in sender:
        contact = sender.split("@", 1)[0]

    summary = subject.strip()[:120]

    return {
        "company": company,
        "quantity": quantity,
        "deadline": deadline,
        "budget": budget,
        "keywords": keywords,
        "contact": contact,
        "summary": summary,
    }


def _render_needs_md(context: dict[str, Any]) -> str:
    env = _load_template_env()
    if env:
        try:
            tpl = env.get_template("needs_summary.md.j2")
            return tpl.render(**context)
        except Exception:
            pass
    # 簡單回退
    ks = ", ".join(context.get("keywords") or [])
    return (
        "# 商務需求彙整\n\n"
        f"- 公司：{context.get('company') or '未明'}\n"
        f"- 聯絡人：{context.get('contact') or '未明'}\n"
        f"- 需求摘要：{context.get('summary') or '未提供'}\n\n"
        "## 關鍵欄位\n"
        f"- 數量：{context.get('quantity') or '未明'}\n"
        f"- 截止：{context.get('deadline') or '未明'}\n"
        f"- 預算：{context.get('budget') or '未明'}\n"
        f"- 關鍵字：{ks or '無'}\n\n"
        "## 建議下一步\n"
        "1. 由業務與對方確認功能範圍與驗收標準\n"
        "2. 安排需求澄清會議並產出會議紀要\n"
        "3. 依會議結論繪製最小可行方案並給出時程與成本\n"
    )


def execute(request: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    參數:
        request: 輸入 JSON（subject/from/body/predicted_label/confidence/attachments）
        context: 可選上下文
    回傳:
        ActionResult dict：含 .md 附件與 meta.next_step
    """
    subject = str(request.get("subject") or "").strip()
    body = str(request.get("body") or "").strip()
    sender = request.get("from")

    req_id = (request.get("meta") or {}).get("request_id") or uuid.uuid4().hex[:12]
    fields = _extract_fields(subject, body, sender)
    md_text = _render_needs_md(fields)

    out_dir = Path("data/output")
    _ensure_dir(out_dir)
    md_name = f"needs_summary_{req_id}.md"
    md_path = out_dir / md_name
    md_path.write_text(md_text, encoding="utf-8")

    attachments = request.get("attachments") or []
    attachments = list(attachments)
    try:
        size = md_path.stat().st_size
    except Exception:
        size = len(md_text.encode("utf-8"))

    attachments.append({"filename": md_name, "size": size})

    meta = dict(request.get("meta") or {})
    meta.update(
        {
            "next_step": "安排需求澄清會議並由業務跟進",
            "confidence": request.get("confidence"),
            "request_id": req_id,
        }
    )

    return {
        "action_name": ACTION_NAME,
        "subject": "[自動回覆] 商務詢問回覆",
        "body": "您好，已收到您的商務需求，附件為彙整內容，將由業務與您聯繫確認細節。",
        "attachments": attachments,
        "meta": meta,
    }


# 兼容不同呼叫名稱
handle = execute
run = execute

if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(execute(payload), ensure_ascii=False))
