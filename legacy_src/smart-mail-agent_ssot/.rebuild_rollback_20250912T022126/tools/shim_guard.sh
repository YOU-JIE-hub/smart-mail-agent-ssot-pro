# minimal guard shim for legacy scripts
guard::die(){ echo "[FATAL] $*" >&2; return 2; }
guard::at_root(){
  # 視為專案根需包含這些任一：src/ 或 Makefile 或 scripts/
  [ -d "./src" ] || [ -f "./Makefile" ] || [ -d "./scripts" ] || guard::die "not at project root: $PWD"
}
guard::abs(){ cd "$1" 2>/dev/null && pwd || echo "$1"; }
