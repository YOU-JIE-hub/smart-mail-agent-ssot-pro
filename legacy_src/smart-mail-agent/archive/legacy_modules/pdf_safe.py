from __future__ import annotations

from pathlib import Path
from typing import Sequence

__all__ = ["_write_minimal_pdf", "write_pdf_or_txt", "_escape_pdf_text"]


def _escape_pdf_text(s: str) -> str:
    s = s or ""
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _sanitize_name(name: str) -> str:
    name = (name or "output").strip().replace("/", "_").replace("\\", "_")
    for ch in '<>:"|?*':
        name = name.replace(ch, "_")
    return name or "output"


def _write_minimal_pdf(lines: Sequence[str], out_dir: str | Path, base_filename: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_sanitize_name(base_filename)}.pdf"
    content = "\n".join(lines or [""]).encode("utf-8")
    with path.open("wb") as f:
        f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        f.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        f.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        f.write(
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        )
        f.write(f"4 0 obj\n<< /Length {len(content)} >>\nstream\n".encode("ascii"))
        f.write(content)
        f.write(b"\nendstream\nendobj\n%%EOF\n")
    return path


def write_pdf_or_txt(lines: Sequence[str], out_dir: str | Path, filename: str) -> Path:
    try:
        return _write_minimal_pdf(lines, out_dir, filename)
    except Exception:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        p = out / f"{_sanitize_name(filename)}.txt"
        p.write_text("\n".join(lines or [""]), encoding="utf-8")
        return p
