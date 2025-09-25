from ai_rpa.mailguard import detect, load_default_ruleset

def test_allow_clean_text():
    out = detect("Hello team, this is a normal inquiry.")
    assert out["verdict"] == "ALLOW"

def test_review_keywords():
    out = detect("Please unsubscribe me from this limited time campaign.")
    assert out["verdict"] in ("REVIEW","BLOCK")
    assert any("kw_review" in r or "kw_block" in r for r in out.get("reasons",[]))

def test_block_suspicious():
    out = detect("Check http://bad.example.top for free money now")
    assert out["verdict"] == "BLOCK"
    assert out["score"] >= 1.0

def test_allowlist_and_blocklist(tmp_path):
    allow = tmp_path/"allow.txt"; allow.write_text("trust.com\n", encoding="utf-8")
    block = tmp_path/"block.txt"; block.write_text("scam.net\n", encoding="utf-8")
    out1 = detect("from: alice@trust.com", headers={"From":"alice@trust.com"}, allowlist_path=allow)
    out2 = detect("from: bob@scam.net", headers={"From":"bob@scam.net"}, blocklist_path=block)
    assert out1["verdict"] == "ALLOW" and "allowlist" in out1["reasons"]
    assert out2["verdict"] == "BLOCK" and "blocklist" in out2["reasons"]
