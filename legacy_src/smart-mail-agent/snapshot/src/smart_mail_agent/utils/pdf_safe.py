from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union


def _safe_stem(name: str) -> str:
    s = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in (name or "output"))
    s = s.strip("._ ")
    return s or "output"


def _escape_pdf_text(s: str) -> str:
    if s is None:
        return ""
    # escape backslash first, then parens; keep newlines; strip control chars
    s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return "".join(ch if ch == "\n" or ord(ch) >= 32 else " " for ch in s)


def _iter_lines(text_or_lines: Any) -> list[str]:
    if isinstance(text_or_lines, (list, tuple)):
        return [str(x) for x in text_or_lines]
    if isinstance(text_or_lines, dict):
        return [str(text_or_lines.get("text") or text_or_lines.get("content") or "")]
    return (str(text_or_lines or "")).splitlines() or [""]


def _norm_text(text_or_lines: Any) -> str:
    if isinstance(text_or_lines, str):
        return text_or_lines
    if isinstance(text_or_lines, dict):
        return str(text_or_lines.get("text") or text_or_lines.get("content") or "")
    if isinstance(text_or_lines, (list, tuple)):
        return "\n".join(str(i) for i in text_or_lines)
    return "" if text_or_lines is None else str(text_or_lines)


def _write_minimal_pdf(
    text_or_lines: Any,
    out_dir: Union[str, Path],
    title: str,
    font_path: Optional[str] = None,
) -> Path:
    """Write a very small multi-line PDF into out_dir/<safe(title)>.pdf, return Path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{_safe_stem(title)}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    font_name = "Helvetica"
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont("NotoSansTC", str(font_path)))
            font_name = "NotoSansTC"
        except Exception:
            pass

    c.setTitle(title)
    c.setFont(font_name, 12)
    width, height = A4
    x, y, leading = 50, height - 72, 16

    for line in _iter_lines(text_or_lines):
        c.drawString(x, y, _escape_pdf_text(line))
        y -= leading
        if y < 50:
            c.showPage()
            c.setFont(font_name, 12)
            y = height - 72
    c.save()
    return pdf_path


def write_text_pdf(
    text: str, output_path: Union[str, Path], font_path: Optional[str] = None
) -> Path:
    """Compat helper: write text directly to a specific .pdf path."""
    out = Path(output_path)
    return _write_minimal_pdf(text, out.parent, out.stem, font_path)


def write_pdf_or_txt(
    text_or_lines: Any,
    output_path: Union[str, Path],
    title_or_font: Optional[str] = None,
) -> Path:
    """
    Back-compat facade:
      - If output_path is a directory: try PDF <dir>/<safe(title)>.pdf; on failure fallback to <dir>/<safe(title)>.txt
      - If output_path endswith .pdf: try PDF; on failure write sibling .txt
      - Else: write plain text file at given path.
    title_or_font is used as the PDF title when applicable.
    """
    out = Path(output_path)

    if out.is_dir():
        title = title_or_font or "output"
        try:
            return _write_minimal_pdf(text_or_lines, out, title, None)
        except Exception:
            txt = out / f"{_safe_stem(title)}.txt"
            txt.write_text(_norm_text(text_or_lines), encoding="utf-8")
            return txt

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".pdf":
        try:
            return _write_minimal_pdf(text_or_lines, out.parent, out.stem, None)
        except Exception:
            txt = out.with_suffix(".txt")
            txt.write_text(_norm_text(text_or_lines), encoding="utf-8")
            return txt

    out.write_text(_norm_text(text_or_lines), encoding="utf-8")
    return out
