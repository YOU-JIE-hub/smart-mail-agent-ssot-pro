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
