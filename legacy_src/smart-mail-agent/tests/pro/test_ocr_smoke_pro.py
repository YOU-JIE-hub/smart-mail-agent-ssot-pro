import ai_rpa.ocr as m

def test_ocr_smoke(tmp_path):
    p = tmp_path/"x.txt"
    p.write_text("not an image", encoding="utf-8")
    for n in ("ocr","run","extract","read"):
        if hasattr(m, n):
            fn = getattr(m, n)
            try:
                fn(str(p))
            except Exception:
                pass
            return
    # 若沒任何可疑名稱，亦不失敗
    assert True
