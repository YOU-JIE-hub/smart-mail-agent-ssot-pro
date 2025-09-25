import os, subprocess, glob
ENV = dict(os.environ, PYTHONNOUSERSITE="1", PYTHONPATH=".:scripts:.sma_tools")
def test_e2e_offline_smoke():
    cmd = ["bash","scripts/sma_e2e_mail.sh","data/demo_eml"]
    subprocess.run(cmd, env=dict(ENV, OFFLINE="1"), check=True, timeout=180)
    cands = sorted(glob.glob("reports_auto/e2e_mail/*"), reverse=True)
    assert cands, "no e2e_mail output dir"
    last = cands[0]
    for name in ("SUMMARY.md","actions.jsonl","cases.jsonl"):
        assert os.path.exists(os.path.join(last,name)), f"missing {name}"
    assert os.path.isdir(os.path.join(last,"rpa_out"))
