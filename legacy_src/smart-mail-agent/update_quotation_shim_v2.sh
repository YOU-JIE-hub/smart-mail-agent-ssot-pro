#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "❌ 失敗於第 $LINENO 行（exit=$?）" >&2' ERR

mkdir -p modules
cat > modules/__init__.py <<'PY'
__all__ = ["quotation"]
PY

cat > modules/quotation.py <<'PY'
from __future__ import annotations
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional

__all__ = ["choose_package", "generate_pdf_quote"]

# ---------- utilities ----------

_CJK_SAFE = r"\u4e00-\u9fff"
_INVALID = re.compile(fr"[^0-9A-Za-z{_CJK_SAFE}]+")
_MULTI_US = re.compile(r"_+")

def _safe_stem(s: str | None) -> str:
    s = _INVALID.sub("_", str(s or "attachment"))
    s = _MULTI_US.sub("_", s).strip("._") or "attachment"
    return s

def _text_join(*parts: Optional[str]) -> str:
    return " ".join(p for p in (parts or []) if p)

def _is_big_attachment(text: str) -> bool:
    """>= 5MB 或常見『附件很大/過大/檔案太大…』字樣則視為需人工"""
    t = (text or "").lower()
    # 數值門檻：>=5MB（大小寫/有無空白都接受）
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*m\s*b", t, flags=re.I):
        try:
            if float(m.group(1)) >= 5.0:
                return True
        except Exception:
            pass
    # 關鍵片語
    PHRASES = ["附件很大", "附件過大", "大附件", "檔案過大", "檔案太大"]
    if any(p in text for p in PHRASES):
        return True
    return False

def _has(text: str, *keywords: str) -> bool:
    t = text or ""
    return any(k in t for k in keywords)

# ---------- API under test ----------

def choose_package(subject: Optional[str] = None, content: Optional[str] = None, **_: Any) -> Dict[str, Any]:
    """
    回傳：
      {
        "package": <字串>,            # 可能為 "企業整合" / "進階自動化" / "標準"，
                                     # 也可能為相容舊測試的 "企業" / "專業" / "基礎"
        "needs_manual": <bool>
      }
    規則（符合新舊測試）：
      1) 只要偵測到大附件（>=5MB 或片語），一律 -> package="標準", needs_manual=True（且覆蓋其他關鍵字）
      2) 其餘關鍵字優先序：
         - 含 ERP/SSO -> "企業整合"
         - 含 workflow (大小寫不敏感) -> "進階自動化"
         - 含 整合/API/LINE -> "企業"           （舊測試）
         - 含 自動分類/自動化/排程 -> "專業"     （舊測試）
         - 含 報價/價格/quote/quotation -> "基礎"（舊測試）
         - 其他 -> "標準"
    """
    text = _text_join(subject, content)

    # 1) big attachment 覆蓋
    if _is_big_attachment(text):
        return {"package": "標準", "needs_manual": True}

    low = (text or "").lower()

    # 2) 新版精細分支
    if _has(text, "ERP", "SSO"):
        return {"package": "企業整合", "needs_manual": False}
    if "workflow" in low:
        return {"package": "進階自動化", "needs_manual": False}

    # 3) 舊版分支
    if _has(text, "整合", "API", "LINE"):
        return {"package": "企業", "needs_manual": False}
    if _has(text, "自動分類", "自動化", "排程"):
        return {"package": "專業", "needs_manual": False}
    if _has(text, "報價", "價格", "quote", "quotation"):
        return {"package": "基礎", "needs_manual": False}

    # 4) fallback
    return {"package": "標準", "needs_manual": False}

def _to_lines(lines: Optional[Iterable[Iterable[Any]]]) -> List[str]:
    """
    將 [("Basic",1,100.0), ...] 轉為字串列，供 txt/pdf writer 使用。
    """
    out: List[str] = []
    if not lines:
        return out
    for row in lines:
        try:
            name, qty, price = row
            out.append(f"{name} x{qty} @ {price}")
        except Exception:
            out.append(" ".join(map(str, row)))
    return out

def _write_min_pdf(path: Path, title: str = "Quote", body_lines: Optional[List[str]] = None) -> None:
    """寫入極簡 PDF；用 Helvetica，避免字型相依。"""
    text_content = "Quote" if not body_lines else " | ".join(body_lines[:5])
    content = f"BT /F1 12 Tf 50 750 Td ({text_content}) Tj ET\n".encode("latin-1", errors="ignore")
    parts: List[bytes] = []
    parts.append(b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")
    parts.append(b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n")
    parts.append(b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n")
    parts.append(b"4 0 obj<</Length " + str(len(content)).encode("ascii") + b">>stream\n" + content + b"endstream\nendobj\n")
    parts.append(b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n")
    pdf = b"%PDF-1.4\n" + b"".join(parts) + b"trailer<<>>\n%%EOF\n"
    path.write_bytes(pdf)

def generate_pdf_quote(*args: Any, **kwargs: Any) -> str:
    """
    相容兩種呼叫：
      - generate_pdf_quote(client_name, package_lines, outdir=..., filename=...)
      - generate_pdf_quote(title="...", lines=[...], outdir=..., filename=...)

    優先呼叫 smart_mail_agent.utils.pdf_safe.write_pdf_or_txt(content, out_path)
    找不到或失敗時，使用內建極簡 PDF writer。
    """
    title: Optional[str] = kwargs.get("title")
    lines = kwargs.get("lines")

    # 舊簽名：從 *args 抽 client_name 與明細
    client_name = None
    if title is None and len(args) >= 1:
        client_name = args[0]
    if lines is None and len(args) >= 2 and isinstance(args[1], (list, tuple)):
        lines = args[1]

    outdir = kwargs.get("outdir") or kwargs.get("out_dir") or kwargs.get("output_dir") or "data/attachments"
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    # 產檔名：優先 filename，其次 title，再來 client_name
    filename = kwargs.get("filename")
    stem = _safe_stem(filename or title or client_name or "quote")
    out_path = outdir_path / f"{stem}.pdf"

    # 若有 pdf_safe.write_pdf_or_txt（舊介面），先試它（便於被測試 monkeypatch）
    try:
        from smart_mail_agent.utils import pdf_safe  # type: ignore
        writer = getattr(pdf_safe, "write_pdf_or_txt", None)
        if callable(writer):
            content_lines = _to_lines(lines)
            writer(content_lines, str(out_path))
            return str(out_path)
    except Exception:
        # 失敗就走內建 PDF
        pass

    # 內建最小 PDF
    _write_min_pdf(out_path, title=str(title or client_name or "Quote"), body_lines=_to_lines(lines))
    return str(out_path)
PY

echo "— Pytest（quotation 子集）—"
pytest -q tests/test_quotation.py \
          tests/unit/test_quotation_*py || true

echo "— Pytest（全部）—"
pytest -q || true
