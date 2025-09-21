import json
from pathlib import Path
from .conftest import run_script

def test_actions_exec_and_post_audit(tmp_path):
    # cases + actions（覆蓋 ticket/diff/faq/quote 四類 + quarantine）
    cases = tmp_path/"cases.jsonl"
    actions = tmp_path/"actions.jsonl"
    outdir = tmp_path/"rpa_out"
    rows = [
        {"id":"t1","subject":"","body":"cannot login","final":"tech_support"},
        {"id":"u1","subject":"","body":"update phone 0912","final":"profile_update"},
        {"id":"p1","subject":"","body":"policy question","final":"policy_qa"},
        {"id":"q1","subject":"","body":"quote NT$3000 by 2025-09-30","final":"biz_quote"},
        {"id":"s1","subject":"","body":"verify http://bad.xyz","final":"complaint"},  # 測試非 spam 類也能進 action
    ]
    cases.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows), encoding="utf-8")
    # 對應的決策（最少一筆 quarantine）
    acts = [
        {"id":"t1","action":"create_support_ticket"},
        {"id":"u1","action":"update_profile"},
        {"id":"p1","action":"send_policy_docs"},
        {"id":"q1","action":"create_quote_ticket"},
        {"id":"s1","action":"quarantine"},
    ]
    actions.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in acts), encoding="utf-8")

    db = tmp_path/"sma.sqlite"
    # 產出企業級產物（不寄信 -> 不加 --send-emails 亦可；這裡測 file outbox）
    run_script(Path("scripts/sma_actions_exec.py"), [
        "--cases", str(cases),
        "--in_actions", str(actions),
        "--out_dir", str(outdir),
        "--db", str(db),
        "--email-mode", "file"
    ])
    # 寫審計與彙總
    rundir = tmp_path/"run_save"
    rundir.mkdir()
    (rundir/"cases.jsonl").write_text(cases.read_text(encoding="utf-8"), encoding="utf-8")
    (rundir/"actions.jsonl").write_text(actions.read_text(encoding="utf-8"), encoding="utf-8")
    run_script(Path("scripts/sma_post_audit.py"), ["--run_dir", str(rundir), "--db", str(db)])

    # 驗證產物
    for sub in ["tickets","diffs","faq_replies","quotes","email_outbox"]:
        assert (outdir/sub).exists()
    assert db.exists()
