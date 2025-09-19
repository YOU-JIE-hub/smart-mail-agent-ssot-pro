#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${1:-$PWD}"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="bundles"
NAME="ssot_bundle_${TS}"
BUNDLE="$OUT/${NAME}.tgz"
mkdir -p "$OUT"

echo "[*] snapshot env/deps…"
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
python -m pip freeze > "$OUT/requirements.lock" || true

echo "[*] make manifest & codebook…"
python tools/make_codebook.py | tee "$OUT/export_meta_${TS}.json" >/dev/null

# 準備待打包檔案清單（排除 .git/.venv/__pycache__/bundles 與 >80MB 的大檔/常見二進位）
python - <<'PY' > bundles/_filelist_${TS}.txt
import os
from pathlib import Path
ROOT=Path.cwd()
SKIP_DIRS={".git",".venv","__pycache__","bundles",".mypy_cache",".pytest_cache",".idea",".vscode"}
BIN_EXT={".safetensors",".pt",".bin",".onnx",".whl",".so",".dylib",".dll",".exe",".pdf",".zip",".gz",".tgz",".xz",".7z",".rar",".jpg",".jpeg",".png",".gif",".pptx",".docx",".xlsx"}
MAX=80*1024*1024
files=[]
for d,sub,fs in os.walk(ROOT):
    dpath=Path(d)
    if any(x in dpath.parts for x in SKIP_DIRS):
        continue
    for f in fs:
        p=dpath/f
        if p.is_symlink():
            files.append(str(p.relative_to(ROOT))); continue
        if p.suffix.lower() in BIN_EXT:
            continue
        if p.stat().st_size>MAX:
            continue
        files.append(str(p.relative_to(ROOT)))
for f in sorted(files):
    print(f)
PY

echo "[*] tar bundle -> $BUNDLE"
tar -czf "$BUNDLE" --files-from "bundles/_filelist_${TS}.txt"

echo "[*] split to 40MB parts (for chat upload)…"
split -b 40m -d -a 3 "$BUNDLE" "${BUNDLE}.part-"
echo "[OK] bundle: $BUNDLE"
echo "[OK] parts : ${BUNDLE}.part-000 …"
echo
echo "To import elsewhere:"
echo "  cat $(basename "$BUNDLE").part-* > $(basename "$BUNDLE")"
echo "  NONINTERACTIVE=1 bash tools/import_bundle.sh $(basename "$BUNDLE")"
