from __future__ import annotations
import time, pathlib
def write_pdf_quote(params:dict) -> str:
    # 需要 reportlab；若 import 失敗讓上層捕捉
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    out_dir=pathlib.Path("reports_auto/actions/quotes"); out_dir.mkdir(parents=True, exist_ok=True)
    fn=str(out_dir/f"{time.strftime('%Y%m%dT%H%M%S')}.pdf")
    c=canvas.Canvas(fn, pagesize=A4)
    x,y=50,800
    c.setFont("Helvetica-Bold",14); c.drawString(x,y,"Quotation"); y-=30
    c.setFont("Helvetica",12)
    for k in ("item","unit_price","qty","subtotal","tax","total","currency","valid_until","subject"):
        c.drawString(x,y,f"{k}: {params.get(k)}"); y-=20
    c.showPage(); c.save(); return fn
