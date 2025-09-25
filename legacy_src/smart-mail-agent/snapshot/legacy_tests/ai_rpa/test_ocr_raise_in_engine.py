import sys
import types

from PIL import Image

from ai_rpa.ocr import run_ocr


def test_ocr_image_to_string_raises(tmp_path, monkeypatch):
    p = tmp_path / "img.png"
    Image.new("RGB", (8, 8), "white").save(p)

    # 構造 pytesseract 並讓其 image_to_string 拋出例外
    fake = types.SimpleNamespace(
        image_to_string=lambda im: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake)

    out = run_ocr(str(p))
    # 例外應被捕捉並回傳空字串（覆蓋最後 except）
    assert out["text"] == ""
