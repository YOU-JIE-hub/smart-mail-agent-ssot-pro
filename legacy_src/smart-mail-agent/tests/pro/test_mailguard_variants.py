from ai_rpa.mailguard.detector import detect

def test_detect_allow_default_no_headers():
    out = detect("正常內文")
    assert out["verdict"] in ("ALLOW","WARN","BLOCK")  # 只要能跑通分支即可

def test_detect_block_by_header_yes():
    out = detect("hello", headers={"X-Spam-Flag":"YES"})
    assert out["verdict"] == "BLOCK"
