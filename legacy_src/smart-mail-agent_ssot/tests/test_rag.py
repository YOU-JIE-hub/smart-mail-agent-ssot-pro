import json
import subprocess
import sys


def test_rag_build_and_query():
    out_build = subprocess.check_output([sys.executable, "-m", "smart_mail_agent.cli.rag_build"])
    j = json.loads(out_build.decode("utf-8"))
    assert "ok" in j
