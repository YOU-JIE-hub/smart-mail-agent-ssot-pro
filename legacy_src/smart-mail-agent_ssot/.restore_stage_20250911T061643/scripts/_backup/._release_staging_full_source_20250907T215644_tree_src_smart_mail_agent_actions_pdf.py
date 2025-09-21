from __future__ import annotations

from typing import Any

from smart_mail_agent.utils.config import paths


def render_quote_pdf(quote: dict[str, Any]) -> dict[str, Any]:
    p = paths()
    out = p.outbox / f"quote_{quote.get('order_id')}.pdf"
    try:
        try:
            from reportlab.lib.pagesizes import A4  # type: ignore
            from reportlab.pdfgen import canvas  # type: ignore
        except Exception as e:  # pragma: no cover
            txt = out.with_suffix(".txt")
            txt.write_text(str(quote), encoding="utf-8")
            return {"ok": True, "pdf_path": str(txt), "format": "txt", "degraded": True, "error": str(e)}
        c = canvas.Canvas(str(out), pagesize=A4)
        t = c.beginText(50, 800)
        t.textLine("報價單 Quote")
        for k in ["order_id", "currency", "amount", "payment_terms", "lead_time_days", "note"]:
            t.textLine(f"{k}: {quote.get(k)}")
        c.drawText(t)
        c.showPage()
        c.save()
        return {"ok": True, "pdf_path": str(out), "format": "pdf"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
