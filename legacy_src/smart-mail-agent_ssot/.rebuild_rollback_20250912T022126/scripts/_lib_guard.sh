guard::at_root() {
  local r="${1:-.}"
  [ -d "$r/src" ] && [ -d "$r/scripts" ] || { echo "[FATAL] not at project root: $PWD"; return 2; }
}
guard::note(){ echo "[NOTE] $*"; }
