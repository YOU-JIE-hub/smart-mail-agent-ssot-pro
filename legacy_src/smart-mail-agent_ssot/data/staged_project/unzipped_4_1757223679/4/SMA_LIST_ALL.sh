#!/usr/bin/env bash
set -euo pipefail
echo "SMA PRINT OK :: LIST ALL"
ROOT_UNIX="${SMA_ROOT:-/home/youjie/projects/smart-mail-agent}"
[ -d "$ROOT_UNIX" ] || { echo "ERROR: 找不到專案根 $ROOT_UNIX"; exit 3; }
cd "$ROOT_UNIX"
OUT="reports_auto/_refactor/list_all_$(date +%Y%m%dT%H%M%S).md"
mkdir -p "$(dirname "$OUT")"; : > "$OUT"
git_ts() { git log -1 --format="%ct" -- "$1" 2>/dev/null || true; }
find "$ROOT_UNIX" -type f \
  \( -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name '*.json' -o -name '*.ini' -o -name 'Makefile' \) \
  ! \( -path '*/.git/*' -o -path '*/venv/*' -o -path '*/.venv/*' -o -path '*/node_modules/*' -o -path '*/dist/*' -o -path '*/out/*' -o -path '*/reports_auto/*' \) \
  -print0 | while IFS= read -r -d '' f; do
    REL="${f#"$ROOT_UNIX/"}"
    SHA="$(sha256sum "$f" 2>/dev/null | awk '{print $1}' || true)"
    if [ -z "${SHA:-}" ]; then
      SHA="$(python3 - "$f" <<'PY'
import sys,hashlib
p=sys.argv[1]; h=hashlib.sha256()
with open(p,'rb') as fp:
    while True:
        b=fp.read(1<<20)
        if not b: break
        h.update(b)
print(h.hexdigest())
PY
)"; fi
    TS="$(git_ts "$REL")"
    GROUP="normal"; [[ "$REL" == src/* ]] && GROUP="src"
    [[ "$REL" == examples/legacy*/* ]] && GROUP="legacy"
    [[ "$REL" == smart_mail_agent/* || "$REL" == ai_rpa/* ]] && GROUP="root_pkg"
    {
      echo "----- FILE-START :: $REL"
      echo "GROUP: $GROUP"
      echo "SHA256: ${SHA:-N/A}"
      echo "GIT_UNIX_TS: ${TS:-N/A}"
      echo "CONTENT-BEGIN >>>"
      cat "$f"
      echo "<<< CONTENT-END"
      echo "----- FILE-END :: $REL"
      echo
    } >> "$OUT"
done
echo "SMA PRINT OK :: LIST DONE -> $OUT"
