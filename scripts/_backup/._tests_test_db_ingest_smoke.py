import subprocess
import sys


def test_pipe_and_db_init_smoke():
    subprocess.check_call([sys.executable, "-m", "smart_mail_agent.pipeline.pipe_run", "--inbox", "samples"])
    subprocess.check_call([sys.executable, "-m", "smart_mail_agent.cli.db_init"])
