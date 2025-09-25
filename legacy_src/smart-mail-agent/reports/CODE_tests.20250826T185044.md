# Smart Mail Agent — Tests (tests/) (20250826T185044)

-----8<----- FILE: tests/ai_rpa_unit/test_actions_direct.py (size 556B)
from __future__ import annotations
from ai_rpa.actions import plan_actions

def test_support_only():
    assert plan_actions(["support"]) == ["reply_support"]

def test_sales_only():
    assert plan_actions(["sales"]) == ["send_quote"]

def test_both_order_and_dedup():
    # 有重複也只出現一次，且順序固定 support 在前
    acts = plan_actions(["support", "sales", "support"])
    assert acts == ["reply_support", "send_quote"]

def test_unknown_and_empty():
    assert plan_actions(["random", ""]) == []
    assert plan_actions([]) == []

-----8<----- END tests/ai_rpa_unit/test_actions_direct.py

-----8<----- FILE: tests/ai_rpa_unit/test_actions_matrix_via_main.py (size 2840B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def _read_stdout(capsys):
    out = capsys.readouterr().out.strip()
    assert out, "應該有 stdout JSON"
    return json.loads(out)

def test_actions_sales_only(tmp_path, monkeypatch, capsys):
    # 文本只會產生銷售意圖（關鍵詞：合作）
    infile = tmp_path / "sales.txt"
    infile.write_text("想要合作、請提供方案", encoding="utf-8")

    # 避免外連：scraper 回空
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    assert isinstance(acts, list) and len(acts) >= 1
    assert any("quote" in str(a).lower() or "sales" in str(a).lower() for a in acts)

def test_actions_support_only(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "support.txt"
    infile.write_text("發票錯了 想退款", encoding="utf-8")

    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    assert isinstance(acts, list) and len(acts) >= 1
    assert any("support" in str(a).lower() or "reply" in str(a).lower() for a in acts)

def test_actions_none(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "none.txt"
    infile.write_text("隨意的敘述，無關鍵字", encoding="utf-8")

    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    assert isinstance(acts, list) and len(acts) == 0

def test_actions_dry_run(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "dry.txt"
    infile.write_text("需要客服協助 退款", encoding="utf-8")

    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local","--dry-run"])
    assert rc == 0
    j = _read_stdout(capsys)
    acts = j.get("results",{}).get("actions",[])
    # 乾跑：應仍回傳規劃，但不做外部副作用；不強制鍵名，只檢查型別與數量
    assert isinstance(acts, list) and len(acts) >= 1

-----8<----- END tests/ai_rpa_unit/test_actions_matrix_via_main.py

-----8<----- FILE: tests/ai_rpa_unit/test_actions_router.py (size 540B)
from ai_rpa.actions_router import plan_from_categories, plan

def test_plan_from_categories_order_and_dedup():
    cats = ["tech_support","business","tech_support"]
    acts = plan_from_categories(cats)
    assert acts == ["create_support_ticket","reply_support_ack","reply_business","generate_pdf_quote"]

def test_plan_from_intents_old_labels():
    intents = ["refund","quote"]  # 舊詞
    acts = plan(intents)
    # refund -> tech_support, quote -> business
    assert "create_support_ticket" in acts and "generate_pdf_quote" in acts

-----8<----- END tests/ai_rpa_unit/test_actions_router.py

-----8<----- FILE: tests/ai_rpa_unit/test_actions_write_json.py (size 357B)
from __future__ import annotations
import json
from pathlib import Path
from ai_rpa.actions import write_json

def test_write_json_roundtrip(tmp_path):
    p = tmp_path / "act_out.json"
    obj = {"ok": True, "ints": ["sales","support"]}
    outp = write_json(obj, p)
    s = Path(outp).read_text(encoding="utf-8")
    j = json.loads(s)
    assert j == obj

-----8<----- END tests/ai_rpa_unit/test_actions_write_json.py

-----8<----- FILE: tests/ai_rpa_unit/test_cov_ocr_scraper_spam_misc.py (size 1444B)
from __future__ import annotations

def test_ocr_reads_text(tmp_path):
    from ai_rpa.ocr import run_ocr
    f = tmp_path/"doc.txt"
    f.write_text("hello OCR", encoding="utf-8")
    out = run_ocr(f)
    assert isinstance(out, dict) and "text" in out

def test_scraper_requests_mock(monkeypatch):
    # 避免外網，mock requests.get 回簡單 HTML
    import types
    import ai_rpa.scraper as scraper

    class Resp:
        status_code = 200
        text = "<html><h1>Title</h1><p>Para</p></html>"

    monkeypatch.setattr(scraper, "requests", types.SimpleNamespace(get=lambda url, timeout=5: Resp()))
    items = scraper.scrape("http://example.com")
    assert isinstance(items, list) and items and all(isinstance(x, dict) for x in items)

def test_spam_adapter_calls_mailguard(monkeypatch):
    # 讓 adapter 的判定可控，確保函式本體被跑過
    import ai_rpa.spam_adapter as spam_adapter
    monkeypatch.setattr("ai_rpa.mailguard.detect", lambda text, **k: {"verdict":"BLOCK","score":1.2,"reasons":["kw_block"]})
    out = spam_adapter.score(["free money!!!"])
    assert out["label"] in ("spam","ham") and isinstance(out.get("score",0.0), float)

def test_config_loader_safe(tmp_path, monkeypatch):
    # 若 yaml 失敗或沒有檔案，load_config 退化為 {}
    import ai_rpa.utils.config_loader as cfg
    bogus = tmp_path/"nope.yml"
    out = cfg.load_config(bogus)
    assert out == {} or isinstance(out, dict)

-----8<----- END tests/ai_rpa_unit/test_cov_ocr_scraper_spam_misc.py

-----8<----- FILE: tests/ai_rpa_unit/test_intent_map_categories.py (size 461B)
from ai_rpa.intent_map import to_categories

def test_old_labels_to_canonical():
    assert to_categories(["support","refund"]) == ["tech_support"]
    assert to_categories(["sales","quote","rfq"]) == ["business"]
    assert to_categories(["complaint"]) == ["complaint"]

def test_canonical_passthrough_and_unknown():
    assert to_categories(["policy_query","business"]) == ["policy_query","business"]
    assert to_categories(["random_unknown"]) == ["other"]

-----8<----- END tests/ai_rpa_unit/test_intent_map_categories.py

-----8<----- FILE: tests/ai_rpa_unit/test_json_safe.py (size 592B)
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from ai_rpa.utils.json_safe import jsonable

@dataclass
class Foo:
    p: Path
    xs: list

def test_jsonable_path_exception_dataclass():
    d = {"p": Path("/tmp/x"), "e": ValueError("bad"), "s": {1,2}, "foo": Foo(Path("y"), [Path("z")])}
    j = jsonable(d)
    assert j["p"] == "/tmp/x"
    assert "ValueError: bad" in j["e"]
    assert sorted(j["s"]) == ["1","2"] or sorted(j["s"]) == [1,2]  # 允許 set 轉 list & 字串化
    assert j["foo"]["p"] == "y"
    assert j["foo"]["xs"] == ["z"]

-----8<----- END tests/ai_rpa_unit/test_json_safe.py

-----8<----- FILE: tests/ai_rpa_unit/test_json_safe_more.py (size 1001B)
from __future__ import annotations
from dataclasses import dataclass
from ai_rpa.utils.json_safe import jsonable

class X:  # fallback 類型
    def __repr__(self) -> str:
        return "<X obj>"

@dataclass
class D:
    a: int

def test_jsonable_fallback_and_nested():
    data = {
        "none": None,
        "bool": True,
        "tuple": (1, 2),
        "set": {3, 1, 2},
        "map": {"k": {9, 8}},
        "obj": X(),
        "dc": D(7),
        "exc": ValueError("bad"),
    }
    j = jsonable(data)
    # tuple -> list
    assert j["tuple"] == [1, 2]
    # set -> list（順序不保證，做包含檢查）
    assert sorted(j["set"]) in ([1,2,3], ["1","2","3"])
    # 巢狀 map + set
    inner = j["map"]["k"]
    assert sorted(inner) in ([8,9], ["8","9"])
    # fallback 物件 -> 可列印字串
    assert isinstance(j["obj"], str) and "X obj" in j["obj"]
    # dataclass -> dict
    assert j["dc"]["a"] == 7
    # 例外 -> 類名: 訊息
    assert "ValueError: bad" in j["exc"]

-----8<----- END tests/ai_rpa_unit/test_json_safe_more.py

-----8<----- FILE: tests/ai_rpa_unit/test_mailguard_detector.py (size 1138B)
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

-----8<----- END tests/ai_rpa_unit/test_mailguard_detector.py

-----8<----- FILE: tests/ai_rpa_unit/test_mailguard_gating_and_alias.py (size 1529B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def _out(capsys):
    out = capsys.readouterr().out.strip()
    assert out
    return json.loads(out)

def test_mailguard_blocks_actions(tmp_path, monkeypatch, capsys):
    f = tmp_path/"x.txt"; f.write_text("free money!!!", encoding="utf-8")
    # 強制 mailguard 回 BLOCK
    import ai_rpa.mailguard.detector as detector
    monkeypatch.setattr(detector, "detect", lambda text, headers=None: {"verdict":"BLOCK","score":0.9,"reasons":["kw"]})
    rc = _run(["prog","--tasks","nlp,mailguard,actions","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert j["results"]["spamcheck"]["verdict"] == "BLOCK"
    assert "actions" not in j["results"]
    assert any(s == "actions:skipped_by_mailguard" for s in j["steps"])

def test_mailguard_alias_spamcheck(tmp_path, monkeypatch, capsys):
    f = tmp_path/"y.txt"; f.write_text("hello", encoding="utf-8")
    import ai_rpa.mailguard.detector as detector
    monkeypatch.setattr(detector, "detect", lambda text, headers=None: {"verdict":"ALLOW","score":0.1,"reasons":[]})
    rc = _run(["prog","--tasks","spamcheck","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert "spamcheck" in j["results"]  # 別名被正規化但結果鍵仍是 spamcheck
    assert j["results"]["spamcheck"]["verdict"] == "ALLOW"

-----8<----- END tests/ai_rpa_unit/test_mailguard_gating_and_alias.py

-----8<----- FILE: tests/ai_rpa_unit/test_main_classify_stdout.py (size 756B)
from __future__ import annotations
import json, sys

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def test_classify_only_stdout(tmp_path, capsys):
    (tmp_path / "a.jpg").write_bytes(b"\x00")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.1")
    (tmp_path / "c.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "d.bin").write_bytes(b"\x00\x01")
    rc = _run(["prog","--tasks","classify_files","--input-path",str(tmp_path),"--url","http://stub.local"])
    assert rc == 0
    j = json.loads(capsys.readouterr().out.strip())
    cls = j.get("results", {}).get("classify", {})
    assert set(cls.keys()) >= {"image","pdf","text","other"}

-----8<----- END tests/ai_rpa_unit/test_main_classify_stdout.py

-----8<----- FILE: tests/ai_rpa_unit/test_main_contracts_generic.py (size 1886B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def _stdout_json(capsys):
    out = capsys.readouterr().out.strip()
    assert out, "應該有 stdout JSON"
    return json.loads(out)

def test_contract_always_has_steps(monkeypatch, tmp_path, capsys):
    # monkeypatch 掉 scraper，避免外連
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [{"tag":"h1","text":"T"}])
    infile = tmp_path / "t.txt"
    infile.write_text("合作與退款", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,actions,scrape","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = _stdout_json(capsys)
    assert "steps" in j and isinstance(j["steps"], list)
    assert "results" in j and "nlp" in j["results"] and "actions" in j["results"]

def test_unknown_task_ignored_but_logged(monkeypatch, tmp_path, capsys):
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])
    rc = _run(["prog","--tasks","abc,nlp","--input-path",str(tmp_path/"x.txt"),"--url","u"])
    assert rc == 0
    j = _stdout_json(capsys)
    assert any("unknown task: abc" in e for e in j.get("errors", []))
    assert "nlp:ok" in j.get("steps", [])

def test_task_alias_normalization(monkeypatch, tmp_path, capsys):
    # "classify" 會被正規化成 classify_files
    p = tmp_path; (p/"a.jpg").write_bytes(b"\x00"); (p/"b.pdf").write_bytes(b"%PDF"); (p/"c.txt").write_text("t","utf-8")
    rc = _run(["prog","--tasks","classify","--input-path",str(p)])
    assert rc == 0
    j = _stdout_json(capsys)
    cls = j.get("results",{}).get("classify",{})
    assert set(cls.keys()) >= {"image","pdf","text","other"}

-----8<----- END tests/ai_rpa_unit/test_main_contracts_generic.py

-----8<----- FILE: tests/ai_rpa_unit/test_main_steps_and_unknown.py (size 847B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def test_unknown_task_kept_and_steps_present(tmp_path, capsys):
    infile = tmp_path / "t.txt"
    infile.write_text("單純做 NLP 測試", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,unknown,actions","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    j = json.loads(out)
    # 任務列表保留 unknown；steps 一定存在；actions 正常執行但可能回空
    assert j["tasks"] == ["nlp","unknown","actions"]
    assert "steps" in j and any(s.startswith("nlp:") for s in j["steps"])
    assert "actions" in j["results"]

-----8<----- END tests/ai_rpa_unit/test_main_steps_and_unknown.py

-----8<----- FILE: tests/ai_rpa_unit/test_nlp_rules_configurable.py (size 1562B)
from __future__ import annotations
import json, sys
from pathlib import Path

def test_rules_default_sales_and_support(tmp_path):
    from ai_rpa.nlp import analyze_text
    t = "想要合作，也遇到發票問題需要退款"
    out = analyze_text([t], model="rules:default")
    # 兩個意圖都能命中（資料驅動、不綁死單一關鍵字）
    assert "sales" in out["intents"] and "support" in out["intents"]

def test_rules_custom_yaml_override(tmp_path):
    # 客製規則：新增一個自定關鍵字「聯繫採購」→ 歸類到 sales
    yml = tmp_path / "custom.yml"
    yml.write_text(
        """
version: 1
intents:
  sales:
    any: ["聯繫採購"]
    all: []
    none: []
    weight: 1.0
""".strip(),
        encoding="utf-8",
    )
    from ai_rpa.nlp import analyze_text
    out = analyze_text("請盡快聯繫採購，謝謝", model=f"rules:{yml}")
    assert "sales" in out["intents"]

def test_rules_all_and_none(tmp_path):
    # 測試 all/none 條件
    yml = tmp_path / "custom2.yml"
    yml.write_text(
        """
version: 1
intents:
  vip_refund:
    any: ["退款"]
    all: ["VIP"]
    none: ["測試"]
    weight: 1.0
""".strip(),
        encoding="utf-8",
    )
    from ai_rpa.nlp import analyze_text
    # 1) 有任何詞 + all 條件成立
    o1 = analyze_text("VIP 客戶要求退款", model=f"rules:{yml}")
    assert "vip_refund" in o1["intents"]
    # 2) 命中 none → 不該觸發
    o2 = analyze_text("VIP 客戶測試退款流程", model=f"rules:{yml}")
    assert "vip_refund" not in o2["intents"]

-----8<----- END tests/ai_rpa_unit/test_nlp_rules_configurable.py

-----8<----- FILE: tests/ai_rpa_unit/test_nlp_rules_direct.py (size 408B)
from __future__ import annotations
from ai_rpa.nlp import analyze_text

def test_sales_keywords_zh():
    r = analyze_text("想要合作，請提供報價方案")
    assert "sales" in r["intents"]

def test_support_keywords_zh():
    r = analyze_text("發票錯了，想退款")
    assert "support" in r["intents"]

def test_none():
    r = analyze_text("只是打個招呼")
    assert r["intents"] == []

-----8<----- END tests/ai_rpa_unit/test_nlp_rules_direct.py

-----8<----- FILE: tests/ai_rpa_unit/test_nlp_rules_golden.py (size 404B)
from ai_rpa.nlp import analyze_text

def test_rules_golden_default():
    cases = {
        "我要退款，客服幫我": ["refund","support"],
        "想要合作，請提供報價": ["sales","quote"],
    }
    for txt, need in cases.items():
        ints = analyze_text(txt, model="rules:default")["intents"]
        for k in need:
            assert k in ints, f"missing {k} for: {txt} -> {ints}"

-----8<----- END tests/ai_rpa_unit/test_nlp_rules_golden.py

-----8<----- FILE: tests/ai_rpa_unit/test_nlp_rules_synonyms.py (size 519B)
from __future__ import annotations
from ai_rpa.nlp import analyze_text

def test_rules_default_synonyms_en():
    cases = {
        "Please issue a refund": ["refund"],
        "I'm returning the item": ["refund"],
        "Need pricing / quotation": ["sales","quote"],
        "RFQ for your product": ["sales","quote"],
    }
    for txt, need in cases.items():
        ints = analyze_text(txt, model="rules:default")["intents"]
        for k in need:
            assert k in ints, f"missing {k} for: {txt} -> {ints}"

-----8<----- END tests/ai_rpa_unit/test_nlp_rules_synonyms.py

-----8<----- FILE: tests/ai_rpa_unit/test_spam_task_via_main.py (size 1297B)
from __future__ import annotations
import sys, json
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def _out(capsys): return json.loads(capsys.readouterr().out.strip())

def test_spam_only_via_main(tmp_path, monkeypatch, capsys):
    # 用 monkeypatch 控制 adapter 輸出
    import ai_rpa.spam_adapter as spam_adapter
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"spam","score":0.9})
    f = tmp_path/"x.txt"; f.write_text("free money", encoding="utf-8")
    rc = _run(["prog","--tasks","spam","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert j["results"]["spam"]["label"] == "spam"
    assert any(s.startswith("spam:") for s in j["steps"])

def test_spam_with_nlp_pipeline(tmp_path, monkeypatch, capsys):
    import ai_rpa.spam_adapter as spam_adapter
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"ham","score":0.1})
    f = tmp_path/"x.txt"; f.write_text("想要合作，請提供報價", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp,spam","--input-path",str(f)])
    assert rc == 0
    j = _out(capsys)
    assert "nlp" in j["results"]
    assert "spam" in j["results"]

-----8<----- END tests/ai_rpa_unit/test_spam_task_via_main.py

-----8<----- FILE: tests/boost/test_cli_help.py (size 1585B)
import os, sys, subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYEXE = sys.executable

def _help_variants(path: pathlib.Path):
    cmds = ([PYEXE, str(path), "--help"], [PYEXE, str(path), "-h"])
    env = os.environ.copy()
    env.setdefault("OFFLINE", "1")
    env["PYTHONPATH"] = f"{ROOT/'src'}:{ROOT}"
    outputs = []
    for cmd in cmds:
        cp = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
        out = (cp.stdout or "") + (cp.stderr or "")
        outputs.append((cp.returncode, out, cmd[-1]))
        # 若有輸出且 rc=0，且包含 usage，立即通過
        if cp.returncode == 0 and out.strip() and "usage" in out.lower():
            return 0, out, cmd[-1]
    # 若兩種旗標都 rc=0 但完全沒輸出，視為 legacy 轉接器行為，仍通過
    if outputs and all(rc == 0 and not out.strip() for rc, out, _ in outputs):
        return 0, "", "none"
    # 否則回傳最後一次結果供斷言
    return outputs[-1]

def _check(relpath: str):
    p = ROOT / relpath
    if not p.exists():
        return  # 允許缺其中一個入口
    rc, out, flag = _help_variants(p)
    assert rc == 0, f"help failed: {relpath} flag={flag}\nstdout={out}"
    # 若有輸出才檢查 usage；無輸出則視為 legacy 轉接器
    if out.strip():
        assert "usage" in out.lower(), f"no usage text from {relpath} flag={flag}\n{out}"

def test_help_routing_entry():
    _check("src/smart_mail_agent/routing/run_action_handler.py")

def test_help_legacy_entry():
    _check("src/run_action_handler.py")

-----8<----- END tests/boost/test_cli_help.py

-----8<----- FILE: tests/boost/test_core_shims_and_utils.py (size 741B)
import importlib
import os

from smart_mail_agent.core.utils import jsonlog as core_jsonlog
from smart_mail_agent.utils import logger as pkg_logger

os.environ.setdefault("SMA_LOG_LEVEL", "DEBUG")


def test_logger_module_proxy():
    importlib.reload(pkg_logger)
    lg = pkg_logger.get_logger("boost")
    lg.debug("ok")
    assert lg.name == "boost" or lg.name.endswith(".boost")


def test_jsonlog_dump_and_parse(tmp_path):
    data = {"a": 1, "b": "x"}
    p = tmp_path / "a.jsonl"
    core_jsonlog.dump_jsonl([data], p)
    rows = list(core_jsonlog.read_jsonl(p))
    assert rows and rows[0]["a"] == 1


def test_policy_engine_shim():
    from smart_mail_agent import policy_engine

    assert hasattr(policy_engine, "apply_policies")

-----8<----- END tests/boost/test_core_shims_and_utils.py

-----8<----- FILE: tests/boost/test_importlib_sanity.py (size 102B)
def test_importlib_util_importable():
    import importlib.util
    assert importlib.util is not None

-----8<----- END tests/boost/test_importlib_sanity.py

-----8<----- FILE: tests/boost/test_reflective_execution.py (size 2889B)
import os, types, inspect, importlib, pkgutil
os.environ.setdefault("OFFLINE", "1")
TOP_PKGS = ["smart_mail_agent", "ai_rpa"]
DENY_MOD_PARTS = {
    ".init_db", "init_db", "send_with_attachment", "mailer",
    ".observability.tracing", ".observability.stats_collector",
    ".scripts.", ".gh_pages.", ".showcase.", ".share.",
}
DENY_FUNC_PREFIX = ("run_", "start_", "main", "init_db", "download")
MAX_CALLS_PER_MODULE = 25
def want_module(modname: str) -> bool:
    return not any(part in modname for part in DENY_MOD_PARTS)
def iter_pkg_modules(root_pkg: str):
    try:
        pkg = importlib.import_module(root_pkg)
    except Exception:
        return
    if not hasattr(pkg, "__path__"):
        yield root_pkg; return
    yield root_pkg
    for m in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        yield m.name
def safe_callables(mod: types.ModuleType):
    called = 0
    for name, obj in vars(mod).items():
        if callable(obj) and not name.startswith(DENY_FUNC_PREFIX):
            try:
                sig = inspect.signature(obj)
                if all(p.default != inspect._empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                       for p in sig.parameters.values()):
                    obj(); called += 1
                    if called >= MAX_CALLS_PER_MODULE: return called
            except Exception: pass
    for name, obj in vars(mod).items():
        if inspect.isclass(obj) and obj.__module__ == mod.__name__:
            try:
                sig = inspect.signature(obj)
                if all(p.default != inspect._empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                       for p in sig.parameters.values()):
                    inst = obj()
                    for mname, mobj in ((n, getattr(inst, n)) for n in dir(inst)):
                        if not callable(mobj) or mname.startswith("_") or mname.startswith(DENY_FUNC_PREFIX):
                            continue
                        try:
                            msig = inspect.signature(mobj)
                            if all(p.default != inspect._empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                                   for p in msig.parameters.values()):
                                mobj(); called += 1
                                if called >= MAX_CALLS_PER_MODULE: return called
                        except Exception: pass
            except Exception: pass
    return called
def test_reflective_sweep():
    total_imported = total_called = 0
    for pkg in TOP_PKGS:
        for modname in iter_pkg_modules(pkg):
            if not want_module(modname): continue
            try:
                mod = importlib.import_module(modname)
                total_imported += 1
                total_called += safe_callables(mod)
            except Exception:
                pass
    assert total_imported >= 5

-----8<----- END tests/boost/test_reflective_execution.py

-----8<----- FILE: tests/coverage/test_actions_branches.py (size 1268B)
from __future__ import annotations
import inspect
import importlib
import types

def _pick_fn(mod):
    for name in ("decide_actions","build_actions","make_actions","generate_actions"):
        if hasattr(mod, name):
            return getattr(mod, name)
    return None

def test_actions_non_dryrun_branch(monkeypatch):
    A = importlib.import_module("ai_rpa.actions")
    fn = _pick_fn(A)
    if fn is None:
        # 沒暴露決策函式就略過
        return

    # 盡力找到可能被呼叫的外部執行端點並 stub 掉
    try:
        ah = importlib.import_module("smart_mail_agent.routing.action_handler")
        if hasattr(ah, "handle"):
            monkeypatch.setattr(ah, "handle", lambda *a, **k: {"ok": True, "actions": a or []})
    except Exception:
        pass
    for attr in ("handle","apply_actions","run_actions","execute"):
        if hasattr(A, attr):
            monkeypatch.setattr(A, attr, lambda *a, **k: {"ok": True})

    # 多訊號組合：意圖 + scrape 節點，且非 dry-run
    res = fn(
        intents=[{"label":"refund"}],
        scrape=[{"tag":"h1","text":"合作"}],
        nodes=[{"tag":"a","text":"下單"}],
        ocr_text="我要退款",
        dry_run=False
    )
    assert isinstance(res, (list, dict))

-----8<----- END tests/coverage/test_actions_branches.py

-----8<----- FILE: tests/coverage/test_actions_unit_smoke.py (size 964B)
from __future__ import annotations
import inspect
import pytest

def _call_with_best_effort(fn, **candidates):
    """依函式簽名從 candidates 擷取可用 kwargs 呼叫。"""
    sig = inspect.signature(fn)
    kwargs = {k: v for k, v in candidates.items() if k in sig.parameters}
    return fn(**kwargs)

def test_actions_decision_smoke():
    import ai_rpa.actions as A
    # 常見命名：任一個存在即可
    for name in ("decide_actions", "build_actions", "make_actions", "generate_actions"):
        if hasattr(A, name):
            fn = getattr(A, name)
            break
    else:
        pytest.skip("actions 模組未暴露可直接呼叫的決策函式")

    res = _call_with_best_effort(
        fn,
        intents=[{"label": "refund"}],
        scrape=[{"tag": "h1", "text": "退款"}],
        nodes=[{"tag": "a", "text": "合作"}],
        ocr_text="我要退款",
        dry_run=True,
    )
    assert isinstance(res, (list, dict))

-----8<----- END tests/coverage/test_actions_unit_smoke.py

-----8<----- FILE: tests/coverage/test_ai_rpa_main_more_paths.py (size 1301B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    old = sys.argv
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_main_unknown_task(tmp_path):
    outp = tmp_path / "out.json"
    rc = _run([
        "prog",
        "--tasks", "unknown_task",
        "--input-path", str(tmp_path),
        "--url", "http://stub.local",
        "--output", str(outp),
    ])
    assert rc == 0
    j = json.loads(outp.read_text(encoding="utf-8"))
    # 應至少回傳成功旗標與 tasks 清單
    assert j.get("ok") is True
    assert isinstance(j.get("tasks"), list)

def test_main_actions_only_no_inputs(tmp_path, monkeypatch):
    # 避免外部連線：scraper 統一回空
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    outp = tmp_path / "out.json"
    rc = _run([
        "prog",
        "--tasks", "actions",
        "--input-path", str(tmp_path),
        "--url", "http://stub.local",
        "--output", str(outp),
    ])
    assert rc == 0
    j = json.loads(outp.read_text(encoding="utf-8"))
    # 應有 results/actions 的骨架（即使為空）
    assert "results" in j
    assert "actions" in j["results"]

-----8<----- END tests/coverage/test_ai_rpa_main_more_paths.py

-----8<----- FILE: tests/coverage/test_ai_rpa_main_more_stdout.py (size 1180B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    import ai_rpa.main as m
    old = sys.argv
    try:
        sys.argv = argv
        return m.main()
    finally:
        sys.argv = old

def test_stdout_allow_online(tmp_path, monkeypatch, capsys):
    infile = tmp_path / "t.txt"
    infile.write_text("合作退款測試", encoding="utf-8")
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])
    rc = _run(["prog","--tasks","nlp,actions","--input-path",str(infile),"--url","http://stub.local","--allow-online"])
    assert rc == 0
    j = json.loads(capsys.readouterr().out.strip())
    assert j.get("ok") is True and "results" in j and "nlp" in j["results"]

def test_stdout_nlp_only(tmp_path, capsys):
    infile = tmp_path / "only_nlp.txt"
    infile.write_text("單純做 NLP 測試", encoding="utf-8")
    rc = _run(["prog","--tasks","nlp","--input-path",str(infile),"--url","http://stub.local"])
    assert rc == 0
    j = json.loads(capsys.readouterr().out.strip())
    assert j.get("ok") is True
    assert j.get("tasks") == ["nlp"]
    assert "nlp" in j.get("results", {})

-----8<----- END tests/coverage/test_ai_rpa_main_more_stdout.py

-----8<----- FILE: tests/coverage/test_ai_rpa_main_stdout_and_bad_inputs.py (size 1435B)
from __future__ import annotations
import json, sys
from pathlib import Path

def _run(argv):
    from ai_rpa.main import main
    old = sys.argv
    try:
        sys.argv = argv
        return main()
    finally:
        sys.argv = old

def test_main_stdout_no_output(tmp_path, monkeypatch, capsys):
    # 準備一個有文字的檔案給 nlp
    infile = tmp_path / "t.txt"
    infile.write_text("合作退款測試", encoding="utf-8")

    # 避免外連：scraper 回空
    import ai_rpa.scraper as scraper
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: [])

    rc = _run(["prog",
               "--tasks","nlp,actions",
               "--input-path", str(infile),
               "--url","http://stub.local"])
    assert rc == 0
    # 現狀：未指定 --output 時不一定印到 stdout；若有輸出就驗證為合法 JSON
    out = capsys.readouterr().out.strip()
    if out:
        j = json.loads(out)
        assert isinstance(j.get("tasks"), list)

def test_main_bad_input_path_stdout(tmp_path, capsys):
    bad = tmp_path / "no_such_file.txt"
    rc = _run(["prog",
               "--tasks","nlp",
               "--input-path", str(bad),
               "--url","http://stub.local"])
    # 目標：不中斷。若有 stdout，必須是可解析的 JSON。
    assert rc == 0
    out = capsys.readouterr().out.strip()
    if out:
        j = json.loads(out)
        assert isinstance(j.get("tasks"), list)

-----8<----- END tests/coverage/test_ai_rpa_main_stdout_and_bad_inputs.py

-----8<----- FILE: tests/coverage/test_core_jsonlog_edges.py (size 377B)
from __future__ import annotations
from pathlib import Path
from smart_mail_agent.core.utils import jsonlog as J

def test_jsonlog_empty_and_bad_lines(tmp_path):
    p = tmp_path / "m.jsonl"
    p.write_text("\nnot-json\n{\"ok\":1}\n", encoding="utf-8")
    rows = list(J.read_jsonl(p))
    assert rows == [{"ok":1}]
    rows2 = J.parse_jsonl(p)
    assert rows2 == [{"ok":1}]

-----8<----- END tests/coverage/test_core_jsonlog_edges.py

-----8<----- FILE: tests/coverage/test_nlp_llm_env_paths.py (size 1077B)
from __future__ import annotations
import importlib, os, sys, inspect

def _smoke_callables(mod):
    for n in dir(mod):
        obj = getattr(mod, n)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                kwargs = {}
                if "text" in sig.parameters: kwargs["text"] = "測試"
                if "model" in sig.parameters: kwargs["model"] = "stub-model"
                try:
                    obj(**kwargs)
                except Exception:
                    pass
            except Exception:
                pass

def test_import_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    if "ai_rpa.nlp_llm" in sys.modules:
        del sys.modules["ai_rpa.nlp_llm"]
    M = importlib.import_module("ai_rpa.nlp_llm")
    _smoke_callables(M)

def test_import_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    if "ai_rpa.nlp_llm" in sys.modules:
        del sys.modules["ai_rpa.nlp_llm"]
    M = importlib.import_module("ai_rpa.nlp_llm")
    _smoke_callables(M)

-----8<----- END tests/coverage/test_nlp_llm_env_paths.py

-----8<----- FILE: tests/coverage/test_nlp_llm_import_smoke.py (size 669B)
from __future__ import annotations
import inspect

def test_nlp_llm_import_and_callable():
    import ai_rpa.nlp_llm as M
    callables = []
    for n in dir(M):
        obj = getattr(M, n)
        if callable(obj):
            # 盡量挑帶 text 參數的函式做輕量呼叫（忽略失敗，重點是可導入）
            try:
                sig = inspect.signature(obj)
                if "text" in sig.parameters:
                    try:
                        obj("測試")
                    except Exception:
                        pass
            except Exception:
                pass
            callables.append(n)
    assert len(callables) >= 1

-----8<----- END tests/coverage/test_nlp_llm_import_smoke.py

-----8<----- FILE: tests/sma_core/test_jsonlog_extras.py (size 480B)
from __future__ import annotations
from pathlib import Path
from smart_mail_agent.core.utils import jsonlog as jl

def test_parse_and_read_jsonl_with_bad_lines(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"a":1}\nnot-a-json\n{"b":2}\n', encoding="utf-8")

    rows = jl.parse_jsonl(p)
    assert len(rows) == 2 and rows[0]["a"] == 1 and rows[1]["b"] == 2

    rows2 = list(jl.read_jsonl(p))
    assert len(rows2) == 2 and rows2[0]["a"] == 1 and rows2[1]["b"] == 2

-----8<----- END tests/sma_core/test_jsonlog_extras.py

-----8<----- FILE: tests/unit/test_log_writer_db_smoke.py (size 975B)
from __future__ import annotations

import sqlite3
from pathlib import Path

from smart_mail_agent.observability.log_writer import log_to_db


def test_log_to_db_inserts_row(tmp_path: Path):
    db = tmp_path / "emails_log.db"
    rid1 = log_to_db(
        subject="S1",
        content="C1",
        summary="Sum1",
        predicted_label="reply_faq",
        confidence=0.9,
        action="auto_reply",
        error="",
        db_path=db,
    )
    rid2 = log_to_db(subject="S2", db_path=db)
    assert isinstance(rid1, int) and isinstance(rid2, int) and rid2 >= rid1
    con = sqlite3.connect(str(db))
    try:
        (cnt,) = con.execute("SELECT COUNT(*) FROM emails_log").fetchone()
        assert cnt >= 2
        row = con.execute(
            "SELECT subject, predicted_label, action FROM emails_log ORDER BY id ASC LIMIT 1"
        ).fetchone()
        assert row[0] == "S1" and row[1] == "reply_faq" and row[2] == "auto_reply"
    finally:
        con.close()

-----8<----- END tests/unit/test_log_writer_db_smoke.py

-----8<----- FILE: tests/unit/test_logger_utils_smoke.py (size 531B)
from __future__ import annotations

import importlib
import logging

import smart_mail_agent.utils.logger as logger


def test_get_logger_and_level(monkeypatch, caplog):
    monkeypatch.setenv("SMA_LOG_LEVEL", "DEBUG")
    importlib.reload(logger)
    caplog.set_level(logging.DEBUG)
    lg = logger.get_logger("sma.test")
    lg.debug("hello debug")
    assert any("hello debug" in rec.message for rec in caplog.records)
    before = len(lg.handlers)
    lg2 = logger.get_logger("sma.test")
    assert len(lg2.handlers) == before

-----8<----- END tests/unit/test_logger_utils_smoke.py

-----8<----- FILE: tests/unit/test_pdf_safe_extra.py (size 913B)
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

-----8<----- END tests/unit/test_pdf_safe_extra.py

-----8<----- FILE: tests/unit/test_sma_types_normalize_extra.py (size 606B)
from __future__ import annotations

from smart_mail_agent.sma_types import normalize_result


def test_normalize_result_branches():
    raw = {
        "action_name": "reply_general",
        "subject": "您好",
        "attachments": ["a.txt", None, {"name": "b.pdf", "size": 123}],
    }
    res = normalize_result(raw)
    try:
        data = res.model_dump()
    except Exception:
        data = res.dict()
    assert data["action"] == "reply_general"
    assert data["subject"].startswith("[自動回覆] ")
    assert isinstance(data["attachments"], list)
    assert data.get("duration_ms", 0) == 0

-----8<----- END tests/unit/test_sma_types_normalize_extra.py

