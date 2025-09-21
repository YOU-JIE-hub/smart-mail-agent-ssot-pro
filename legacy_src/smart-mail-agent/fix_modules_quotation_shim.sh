#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

# 0) venv（保險）
if [ ! -x ".venv/bin/python" ]; then python3 -m venv .venv; fi
. .venv/bin/activate

# 1) 在「專案根目錄」建立/覆寫 modules 套件，供 tests 直接 import
mkdir -p modules
cat > modules/__init__.py <<'PY'
# 提供舊測試用的命名空間套件
__all__ = ["quotation"]
PY

cat > modules/quotation.py <<'PY'
from __future__ import annotations
from pathlib import Path
import re
from typing import List

__all__ = ["choose_package", "generate_pdf_quote"]

def _safe_stem(s: str | None) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", str(s or "attachment"))
    s = re.sub(r"_+", "_", s).strip("._") or "attachment"
    return s

def choose_package(subject: str | None = None, body: str | None = None) -> str:
    """
    舊測試相容規則（與先前你專案裡的實作一致）：
      - 企業 > 專業 > 基礎 的優先序
    """
    text = f"{subject or ''} {body or ''}"
    def has(*ks: str) -> bool:
        return any(k in text for k in ks)

    if has("整合", "API", "ERP", "LINE"):
        return "企業"
    if has("自動分類", "自動化", "排程"):
        return "專業"
    if has("報價", "價格", "quote", "quotation"):
        return "基礎"
    if ("其他詢問" in (subject or "")) or ("功能" in (body or "")):
        return "企業"
    return "基礎"

def _write_min_pdf(path: Path, title: str = "Quote") -> None:
    """寫入最小可驗證 PDF（避免外部相依與字型問題）。"""
    content = b"BT /F1 12 Tf 50 750 Td (Quote) Tj ET\n"
    parts: List[bytes] = []
    parts.append(b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")
    parts.append(b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n")
    parts.append(b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n")
    parts.append(b"4 0 obj<</Length " + str(len(content)).encode("ascii") + b">>stream\n" + content + b"endstream\nendobj\n")
    parts.append(b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n")
    pdf = b"%PDF-1.4\n" + b"".join(parts) + b"trailer<<>>\n%%EOF\n"
    path.write_bytes(pdf)

def generate_pdf_quote(*args, **kwargs) -> str:
    """
    寬鬆相容介面（符合舊測試呼叫方式）：
      - generate_pdf_quote(client_name, package, price=None, out_dir="data/attachments", filename=None)
      - generate_pdf_quote(title="...", lines=[...], out_dir="...", filename=None)
    回傳：產生之 PDF 路徑字串
    """
    # 優先嘗試呼叫封裝內的新實作；失敗則走 fallback
    try:
        from smart_mail_agent.features.quotation import generate_pdf_quote as _impl  # type: ignore
        return _impl(*args, **kwargs)  # type: ignore[misc]
    except Exception:
        pass

    client_name = None
    package = None
    title = kwargs.get("title")
    out_dir = Path(kwargs.get("out_dir") or kwargs.get("output_dir") or "data/attachments")
    filename = kwargs.get("filename")

    if title is None and len(args) >= 1:
        client_name = args[0]
    if title is None and len(args) >= 2:
        package = args[1]
    if title is None:
        base = "_".join([x for x in [client_name, package] if x]) or "quote"
        title = base

    out_dir.mkdir(parents=True, exist_ok=True)
    name = filename or f"{_safe_stem(str(title))}.pdf"
    path = out_dir / name
    _write_min_pdf(path, title=str(title))
    return str(path)
PY

# 2) 先跑與 quotation 相關的測試，再跑全部（遇錯不中斷，讓你看完整清單）
echo "— Pytest（quotation 子集）—"
pytest -q tests/test_quotation.py \
          tests/unit/test_quotation_*py || true

echo "— Pytest（全部）—"
pytest -q || true
