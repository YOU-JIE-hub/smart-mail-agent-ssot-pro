# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import re, shutil, time, pathlib, os
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
(root/"reports_auto/hotfix_backups"/ts).mkdir(parents=True, exist_ok=True)
bakdir=root/"reports_auto/hotfix_backups"/ts

mk=root/"Makefile"
if mk.exists():
    data=mk.read_text(encoding="utf-8", errors="ignore")
    shutil.copy2(mk, bakdir/"Makefile.bak")
    def patch_train_block(text, name):
        pat=rf"(?ms)^\\s*{name}:\\n(?:\\t.*\\n)+"
        repl=f"{name}:\n\t@echo \"[INFO] {name} is placeholder. No local train script. Use external pipeline or set ENV to models.\"\n"
        return re.sub(pat, repl, text)
    for tgt in ("train-intent","train-spam","train-kie"):
        data=patch_train_block(data, tgt)
    mk.write_text(data, encoding="utf-8")

readme=root/"README.md"
if not readme.exists():
    readme.write_text("""# Smart Mail Agent — Minimal Ops README

## 快速開始
```bash
cd ~/projects/smart-mail-agent-ssot-pro
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="$PWD:${PYTHONPATH:-}"

export INTENT_PKL="$HOME/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl"
export SPAM_PKL="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export KIE_DIR="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model"

# 任何指令一律用 panic 包起來
bash tools/panic.sh ". .venv/bin/activate; python3 scripts/eval_all.py --cfg configs/model_paths.yaml"
train-* 目標目前為安全占位；以「外部提供模型＋ENV 綁定」為主。
""", encoding="utf-8")
print("[OK] Makefile patched; README prepared at", readme)
PY
- LOG  : reports_auto/panic_20250921T121244/run.log
- ERR  : reports_auto/panic_20250921T121244/run.err
- PY   : reports_auto/panic_20250921T121244/python_stderr.txt
- OOM  : reports_auto/panic_20250921T121244/oom.txt
- TRACE: reports_auto/panic_20250921T121244/xtrace.sh
- SYS  : reports_auto/panic_20250921T121244/system.txt

## Heuristics
