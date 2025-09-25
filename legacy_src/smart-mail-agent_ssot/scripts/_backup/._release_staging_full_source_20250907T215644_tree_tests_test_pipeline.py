import glob
import json
import subprocess
import sys


def test_pipeline_green():
    subprocess.check_call([sys.executable, "-m", "smart_mail_agent.pipeline.pipe_run", "--inbox", "samples"])
    files = sorted(glob.glob("reports_auto/status/PIPE_SUMMARY_*.json"))
    assert files, "no PIPE_SUMMARY produced"
    with open(files[-1], encoding="utf-8") as f:
        data = json.load(f)
    assert data["distribution"]["done"] == 10
