# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import re, shutil, time, pathlib
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
bakdir=root/("reports_auto/hotfix_backups/"+ts); bakdir.mkdir(parents=True, exist_ok=True)

mk=root/"Makefile"
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
readme.write_text("""# Smart Mail Agent — Minimal Ops README

## 快速開始
1) 先進專案根並啟用 venv（以下指令示例已內建這一步）。
2) 三個環境變數綁定你本機的模型路徑（Intent/Spam/KIE）。
3) 任何指令一律用 panic 包起來，錯誤匯流到 reports_auto/panic_*。

### 三個環境變數（綁定你的本機模型）
export INTENT_PKL="$HOME/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl"
export SPAM_PKL="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export KIE_DIR="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model"

### 總評（會產生 reports_auto/summary.json）
bash tools/panic.sh ". .venv/bin/activate; python3 scripts/eval_all.py --cfg configs/model_paths.yaml && echo --- summary --- && sed -n 1,200p reports_auto/summary.json"

### API 啟動（如需）
bash tools/panic.sh ". .venv/bin/activate; uvicorn scripts.api_meta:app --host 127.0.0.1 --port 8088"

### 注意
- Makefile 的 train-* 目前為安全占位；此專案以「外部提供模型＋ENV 綁定」為主。
""", encoding="utf-8")

print("[OK] Makefile patched and README.md created. Backup:", bakdir)
PY
- LOG  : reports_auto/panic_20250921T114137/run.log
- ERR  : reports_auto/panic_20250921T114137/run.err
- PY   : reports_auto/panic_20250921T114137/python_stderr.txt
- OOM  : reports_auto/panic_20250921T114137/oom.txt
- TRACE: reports_auto/panic_20250921T114137/xtrace.sh
- SYS  : reports_auto/panic_20250921T114137/system.txt

## Heuristics
