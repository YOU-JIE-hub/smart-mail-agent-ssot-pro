from __future__ import annotations
import os, sys, subprocess, time
from pathlib import Path

def run_e2e_mail(eml_dir: str, out_dir: str, db_path: str = "db/sma.sqlite",
                 ndjson_path: str = "reports_auto/logs/pipeline.ndjson") -> None:
    """Safe proxy: do nothing heavy at import; just delegate to legacy runner."""
    root = Path(__file__).resolve().parents[3]  # project root
    py = sys.executable
    env = os.environ.copy()
    env.setdefault("SMA_ROOT", str(root))
    env.setdefault("SMA_RUN_TS", time.strftime("%Y%m%dT%H%M%S"))
    # prepare observable paths
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(ndjson_path).parent.mkdir(parents=True, exist_ok=True)
    legacy = root / "scripts" / "sma_e2e_mail.py"
    if not legacy.exists():
        raise FileNotFoundError(f"legacy runner not found: {legacy}")
    subprocess.run([py, "-u", str(legacy), str(eml_dir)], check=True, env=env)

if __name__ == "__main__":
    print("run_action_handler: OK")
