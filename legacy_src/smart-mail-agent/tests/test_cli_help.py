import subprocess, os
ENV = dict(os.environ, PYTHONNOUSERSITE="1", PYTHONPATH=".:scripts:.sma_tools")
def _ok(cmd): subprocess.run(cmd, env=ENV, check=True, timeout=30,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
def test_quick_eval_help(): _ok(["python","scripts/sma_quick_eval.py","--help"])
def test_e2e_run_help():    _ok(["python","scripts/sma_e2e_run.py","--help"])
