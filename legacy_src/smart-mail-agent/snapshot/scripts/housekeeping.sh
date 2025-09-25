#!/usr/bin/env bash
# Housekeeping: 安全、不中斷版本（失敗只警告）
set -uo pipefail
shopt -s nullglob dotglob

DRY="${DRY_RUN:-1}"   # 1 = dry-run, 0 = apply
GREEN='\033[0;32m'; YEL='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
say(){ echo -e "${GREEN}[*]${NC} $*"; }
warn(){ echo -e "${YEL}[!]${NC} $*"; }
die(){ echo -e "${RED}[x]${NC} $*"; exit 1; }

step(){  # step "描述" "指令..."
  local msg="$1"; shift
  say "$msg"
  if [[ "$DRY" == "1" ]]; then
    echo "  DRY-RUN: $*"
    return 0
  fi
  eval "$@"; local rc=$?
  if (( rc != 0 )); then
    warn "命令失敗（$rc），已略過：$*"
  fi
}
must(){  # must "描述" "指令..."（失敗才終止）
  local msg="$1"; shift
  say "$msg"
  if [[ "$DRY" == "1" ]]; then
    echo "  DRY-RUN: $*"
    return 0
  fi
  if ! eval "$@"; then
    die "致命錯誤，停止：$*"
  fi
}

must "確認位於 Git repo" "git rev-parse --is-inside-work-tree >/dev/null 2>&1"

say "更新 .gitignore 規則"
read -r -d '' IGNORES <<'TXT'
# --- repo housekeeping (auto) ---
/.coverage
/coverage.xml
/reports/*
!reports/.gitkeep

/data/output/*
/data/tmp/*
/data/**/*.db
/data/**/*.sqlite
/data/**/*.csv

/out/*
!/out/.gitkeep

/share/*.txt
*.bak.*
*.bak
*.orig
*.rej

# generated artifacts
/quote.pdf
/quote_pdf.pdf
/.local-logs/*
TXT
if ! grep -q "repo housekeeping (auto)" .gitignore 2>/dev/null; then
  step "追加 .gitignore 規則" "printf '%s\n' \"\$IGNORES\" >> .gitignore"
else
  warn ".gitignore 已含自動區塊，略過"
fi

say "更新 .gitattributes（行尾/二進位）"
read -r -d '' ATTRS <<'TXT'
* text=auto eol=lf
*.ttf binary
*.otf binary
*.woff binary
*.woff2 binary
*.pdf binary
*.png binary
*.jpg binary
*.jpeg binary
TXT
if [[ ! -f .gitattributes ]] || ! grep -q "text=auto eol=lf" .gitattributes; then
  step "寫入 .gitattributes" "printf '%s\n' \"\$ATTRS\" >> .gitattributes"
else
  warn ".gitattributes 已有設定，略過"
fi

# 確保 .gitkeep 存在且可被追蹤
step "建立 out/ 與 reports/ 的 .gitkeep" "mkdir -p out reports && touch out/.gitkeep reports/.gitkeep && git add -f out/.gitkeep reports/.gitkeep"

# 去重多餘 PR template
[[ -f ".github/PULL_REQUEST_TEMPLATE.md" ]] && step "移除 .github/PULL_REQUEST_TEMPLATE.md" "git rm -f .github/PULL_REQUEST_TEMPLATE.md || true"
[[ -f "PULL_REQUEST_TEMPLATE.md" ]] && step "移除根目錄 PULL_REQUEST_TEMPLATE.md" "git rm -f PULL_REQUEST_TEMPLATE.md || true"
[[ -f ".github/pull_request_template.md" ]] && step "移除 .github/pull_request_template.md" "git rm -f .github/pull_request_template.md || true"

# 友善處理 .env 樣板更名（有追蹤用 git mv；否則 fallback mv）
if [[ -f ".env.smtp-test" ]]; then
  if git ls-files --error-unmatch .env.smtp-test >/dev/null 2>&1; then
    step "將 .env.smtp-test → .env.smtp.example (git mv)" "git mv .env.smtp-test .env.smtp.example"
  else
    step "將 .env.smtp-test → .env.smtp.example (mv)" "mv .env.smtp-test .env.smtp.example"
  fi
fi

say "從 Git 索引移除生成物/暫存/備份（工作區保留）"
step "移除常見生成物" "git rm -rf --cached --ignore-unmatch data/output/* out/quote*.pdf .coverage coverage.xml .local-logs/* share/*.txt assert"
step "移除備份類" "git rm -f --cached --ignore-unmatch .pre-commit-config.yaml.bak.* .ruff.toml.bak.*"

say '產出乾淨樹狀到 share/tree_full.txt'
step "建立 share/ 夾" "mkdir -p share"
if [[ "$DRY" == "1" ]]; then
  echo "  DRY-RUN: 會寫入 share/tree_full.txt（實際執行時生成）"
else
  PYBIN="$(command -v python3 || command -v python || true)"
  [[ -n "$PYBIN" ]] || die "找不到 python/python3"
  TMPF="$(mktemp)"
  {
    echo "ROOT: $(pwd)"
    "$PYBIN" - <<'PY'
from pathlib import Path
EXC={".git",".venv","__pycache__",".pytest_cache",".mypy_cache",".ruff_cache","node_modules","dist","build","data/output","out"}
def walk(d:Path,prefix=""):
    xs=sorted([p for p in d.iterdir() if p.name not in EXC], key=lambda p:(p.is_file(),p.name.lower()))
    for i,p in enumerate(xs):
        conn="└── " if i==len(xs)-1 else "├── "
        print(prefix+conn+p.name+("/" if p.is_dir() else ""))
        if p.is_dir():
            walk(p, prefix+("    " if i==len(xs)-1 else "│   "))
walk(Path("."))
PY
  } >> "$TMPF" || warn "生成樹狀快照時有警告"
  mv "$TMPF" share/tree_full.txt
  say "已寫入 share/tree_full.txt"
fi

if [[ "$DRY" == "0" ]]; then
  say "建立整理 commit（若有變更）"
  git add -f out/.gitkeep reports/.gitkeep .gitignore .gitattributes || true
  git add -A || true
  if ! git diff --cached --quiet --ignore-submodules --; then
    git commit -m "chore(repo): housekeeping — ignore generated artifacts, unify PR template, normalize env & attrs" || warn "commit 失敗或無變化"
  else
    warn "沒有 staging 的變更可提交，略過 commit"
  fi
fi

say "完成 ✅（DRY_RUN=${DRY})"
