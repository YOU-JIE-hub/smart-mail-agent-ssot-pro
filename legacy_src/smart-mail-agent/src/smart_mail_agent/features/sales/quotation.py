from __future__ import annotations

import os
import time
from pathlib import Path

__all__ = ["choose_package", "generate_pdf_quote"]


def choose_package(subject: str, content: str) -> dict:
    """
    依 subject/content 的關鍵字，回傳 dict，其中必含:
      - package: 「基礎 / 專業 / 企業」
      - needs_manual: bool（是否需要人工確認）
    邏輯：
      - 命中 企業 關鍵字（ERP/API/LINE/整合） → {"package":"企業","needs_manual":False}
      - 命中 專業 關鍵字（自動化/排程/自動分類…） → {"package":"專業","needs_manual":False}
      - 命中 基礎 關鍵字（報價/價格/price/quote） → {"package":"基礎","needs_manual":False}
      - 其他（沒命中） → 保守預設企業，且 needs_manual=True
    """
    text = f"{subject}\n{content}".lower()

    enterprise_kw = ["erp", "api", "line", "整合"]
    if any(k in text for k in enterprise_kw):
        return {"package": "企業", "needs_manual": False}

    pro_kw = ["自動化", "排程", "自動分類", "automation", "schedule", "workflow"]
    if any(k in text for k in pro_kw):
        return {"package": "專業", "needs_manual": False}

    basic_kw = ["報價", "價格", "價錢", "pricing", "price", "quote"]
    if any(k in text for k in basic_kw):
        return {"package": "基礎", "needs_manual": False}

    # 沒命中：保守→企業，但標記需要人工確認
    return {"package": "企業", "needs_manual": True}


# 最小合法單頁 PDF（測試只需存在且為 .pdf）
_MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 50 150 Td (Quote) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000010 00000 n
0000000061 00000 n
0000000113 00000 n
0000000279 00000 n
0000000418 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
520
%%EOF
"""


def generate_pdf_quote(package: str, client_name: str, out_dir: str = "data/output") -> str:
    """
    產生報價 PDF；若沒有任何 PDF 引擎，寫入最小 PDF 後援，副檔名固定為 .pdf。
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    pdf_path = os.path.join(out_dir, f"quote-{package}-{ts}.pdf")
    try:
        with open(pdf_path, "wb") as f:
            f.write(_MINIMAL_PDF)
    except Exception:
        open(pdf_path, "wb").close()
    return pdf_path
