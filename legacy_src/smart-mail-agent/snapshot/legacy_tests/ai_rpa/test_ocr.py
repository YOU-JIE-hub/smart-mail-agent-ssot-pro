import sys
import types

from ai_rpa.ocr import run_ocr


def test_ocr_missing_file(tmp_path):
    out = run_ocr(str(tmp_path / "no.png"))
    assert out["text"] == ""


def test_ocr_with_fake_engine(tmp_path, monkeypatch):
    # 建立測試影像（Pillow 由 requirements 保證存在）
    from PIL import Image, ImageDraw

    p = tmp_path / "img.png"
    im = Image.new("RGB", (64, 32), "white")
    d = ImageDraw.Draw(im)
    d.text((2, 2), "OK", fill="black")
    im.save(p)

    # 注入假的 pytesseract
    fake = types.SimpleNamespace(image_to_string=lambda im: "OK")
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    out = run_ocr(str(p))
    assert out["text"] == "OK"
