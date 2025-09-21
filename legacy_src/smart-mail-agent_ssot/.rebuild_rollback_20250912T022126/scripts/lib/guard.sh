#!/usr/bin/env bash
guard::at_root() {
  local here="$PWD"
  for d in src scripts tools; do
    if [ ! -d "$d" ]; then
      echo "[GUARD] not at repo root: $here (missing $d)" >&2
      return 1
    fi
  done
  export ROOT="$PWD"
  return 0
}
guard::need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[GUARD] need cmd: $1" >&2; return 1; }; }
guard::need_file() { [ -f "$1" ] || { echo "[GUARD] need file: $1" >&2; return 1; }; }
