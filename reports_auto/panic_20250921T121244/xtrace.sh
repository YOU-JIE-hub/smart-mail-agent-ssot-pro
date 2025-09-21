+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
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
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
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
PY' ']'
+ echo '== SNAPSHOT 20250921T121244 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 - <<'\''PY'\''
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
PY'
++ tee -a reports_auto/panic_20250921T121244/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\''
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
PY'
+ echo '- LOG  : reports_auto/panic_20250921T121244/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T121244/run.err'
+ echo '- PY   : reports_auto/panic_20250921T121244/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T121244/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T121244/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T121244/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T121244/run.err reports_auto/panic_20250921T121244/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T121244/run.err reports_auto/panic_20250921T121244/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T121244/run.err reports_auto/panic_20250921T121244/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T121244/run.err reports_auto/panic_20250921T121244/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T121244/REPORT.md\nreports_auto/panic_20250921T121244/run.log\nreports_auto/panic_20250921T121244/run.err\nreports_auto/panic_20250921T121244/python_stderr.txt\nreports_auto/panic_20250921T121244/xtrace.sh\nreports_auto/panic_20250921T121244/system.txt\nreports_auto/panic_20250921T121244/oom.txt\n'
+ exit 0
