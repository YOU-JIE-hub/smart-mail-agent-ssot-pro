import os
import textwrap

from ai_rpa.utils.config_loader import load_config


def test_load_config_and_env_fallback(tmp_path):
    yml = tmp_path / "cfg.yaml"
    yml.write_text(
        textwrap.dedent(
            """
    input_path: "in"
    output_path: "out.json"
    tasks: ["ocr"]
    nlp: {model: "offline-keyword"}
    """
        ).strip(),
        encoding="utf-8",
    )
    os.environ.pop("FONTS_PATH", None)
    os.environ.pop("PDF_OUTPUT_DIR", None)
    cfg = load_config(str(yml))
    assert cfg["input_path"] == "in"
    assert cfg["nlp"]["model"] == "offline-keyword"
    assert "fonts_path" in cfg and "pdf_output_dir" in cfg


def test_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("FONTS_PATH", "f.ttf")
    monkeypatch.setenv("PDF_OUTPUT_DIR", "pdfdir")
    cfg = load_config(None)
    assert cfg["fonts_path"] == "f.ttf"
    assert cfg["pdf_output_dir"] == "pdfdir"
