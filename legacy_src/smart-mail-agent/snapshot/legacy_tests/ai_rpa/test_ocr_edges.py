import builtins

from ai_rpa import ocr as ocr_mod


def test_ocr_no_pillow(monkeypatch, tmp_path):
    orig_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("no PIL")
        return orig_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = ocr_mod.run_ocr(str(tmp_path / "x.png"))
    assert out["text"] == ""


def test_ocr_no_pytesseract_with_image(monkeypatch, tmp_path):
    # 產生可開啟的影像
    from PIL import Image

    p = tmp_path / "ok.png"
    Image.new("RGB", (8, 8), "white").save(p)
    # 禁用 pytesseract 匯入
    orig_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "pytesseract" or name.startswith("pytesseract."):
            raise ImportError("no pytesseract")
        return orig_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = ocr_mod.run_ocr(str(p))
    assert out["text"] == ""  # 走到 pytesseract None 的退化分支


def test_ocr_image_open_failure(monkeypatch, tmp_path):
    # 確保有 PIL，但令 Image.open 拋例外
    from PIL import Image

    def boom(*a, **k):
        raise RuntimeError("open failed")

    monkeypatch.setattr(Image, "open", boom)
    out = ocr_mod.run_ocr(str(tmp_path / "x.png"))
    assert out["text"] == ""  # 命中最後的 except 分支
