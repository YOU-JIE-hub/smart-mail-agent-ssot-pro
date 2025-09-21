# Panic Report
- Exit code: 1
- CMD  : python3 - <<PY
import re, shutil, time, pathlib, sys
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
bakdir=root/("reports_auto/hotfix_backups/"+ts); bakdir.mkdir(parents=True, exist_ok=True)

mk=root/"Makefile"
data=mk.read_text(encoding="utf-8", errors="ignore")
shutil.copy2(mk, bakdir/"Makefile.bak")

# 將 train-* 目標改為安全占位（回報缺件而不失敗）
def patch_train_block(text, name):
    pat=rf"(?ms)^\\s*{name}:\\n(?:\\t.*\\n)+"
    repl=f"{name}:\n\t@echo \"[INFO] {name} is placeholder. No local train script. Use external pipeline or set ENV to models.\"\n"
    return re.sub(pat, repl, text)

for tgt in ("train-intent","train-spam","train-kie"):
    data=patch_train_block(data, tgt)

mk.write_text(data, encoding="utf-8")

readme=root/"README.md"
readme.write_text(f"""# Smart Mail Agent — Minimal Ops README

## 快速開始
```bash
# 先進專案根與 venv
cd ~/projects/smart-mail-agent-ssot-pro
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="$PWD:${PYTHONPATH:-}"

# 三個環境變數（綁定你的本機模型）
export INTENT_PKL="$HOME/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl"   # Intent=6類
export SPAM_PKL="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"  # Spam=0/1
export KIE_DIR="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model"

# 任何指令一律用 panic 包起來
bash tools/panic.sh "python scripts/eval_all.py --cfg configs/model_paths.yaml"
可用指令
make env：建立虛擬環境並安裝相依

make eval-all：匯整 Intent/Spam/KIE 檢查，輸出 reports_auto/summary.json

make api：啟動 uvicorn scripts.api_meta:app --port 8088

注意：train-* 目標目前為安全占位；此專案以「外部提供模型＋ENV 綁定」為主。
""", encoding="utf-8")
print("[OK] Makefile patched and README.md created. Backup:", bakdir)
PY
- LOG  : reports_auto/panic_20250921T112816/run.log
- ERR  : reports_auto/panic_20250921T112816/run.err
- PY   : reports_auto/panic_20250921T112816/python_stderr.txt
- OOM  : reports_auto/panic_20250921T112816/oom.txt
- TRACE: reports_auto/panic_20250921T112816/xtrace.sh
- SYS  : reports_auto/panic_20250921T112816/system.txt

## Heuristics
