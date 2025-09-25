from __future__ import annotations

from pathlib import Path

import smart_mail_agent.utils.pdf_safe as pdf_safe


def test_escape_pdf_text_basic():
    s = pdf_safe._escape_pdf_text(r"A(B) \ tail")
    assert r"A\(" in s and r"\)" in s and r"\\" in s


def test_write_pdf_or_txt_pdf_success(tmp_path: Path):
    out = pdf_safe.write_pdf_or_txt(["Hello", "世界"], tmp_path, "報 價?單")
    p = Path(out)
    assert p.exists()
    assert p.suffix in {".pdf", ".txt"}
    assert "?" not in p.name


def test_write_pdf_or_txt_txt_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        pdf_safe,
        "_write_minimal_pdf",
        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    out = pdf_safe.write_pdf_or_txt(["X"], tmp_path, "weird/name?.pdf")
    p = Path(out)
    assert p.exists() and p.suffix == ".txt"
    assert p.read_text(encoding="utf-8").strip() == "X"
