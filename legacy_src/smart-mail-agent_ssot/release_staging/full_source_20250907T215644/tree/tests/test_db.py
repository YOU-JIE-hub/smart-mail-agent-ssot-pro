import subprocess
import sys


def test_db_guard_pass():
    subprocess.check_call([sys.executable, "-m", "smart_mail_agent.pipeline.pipe_run", "--inbox", "samples"])
    subprocess.check_call([sys.executable, "-m", "smart_mail_agent.cli.db_init"])
