#!/usr/bin/env bash
set -Eeuo pipefail

# ===== 可調參數 =====
ROOTS_DEFAULT="$HOME $HOME/projects/smart-mail-agent_ssot"
ROOTS="${ROOTS:-$ROOTS_DEFAULT}"

LOG_OLDER_THAN_DAYS="${LOG_OLDER_THAN_DAYS:-10}"
ALLOW_NODE="${ALLOW_NODE:-0}"     # 1 會刪 node_modules/
ALLOW_APT="${ALLOW_APT:-0}"       # 1 會清 APT 快取（需 sudo）
DRY_RUN="${DRY_RUN:-0}"           # 1 只列出不刪除
# ====================

TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="reports_auto/cleanup/${TS}"
mkdir -p "$OUTDIR"
REPORT="$OUTDIR/cleanup_summary.txt"
DELETED_LIST="$OUTDIR/deleted.list"
CANDIDATE_LIST="$OUTDIR/candidates.list"
ERR_LOG="$OUTDIR/error.log"

exec 3>"$ERR_LOG"  # 錯誤另存

human() {
  local n=$1 u=(B KB MB GB TB PB) i=0
  [[ -z "$n" ]] && { echo "0 B"; return; }
  while (( n >= 1024 && i < ${#u[@]}-1 )); do n=$((n/1024)); ((i++)); done
  echo "${n} ${u[$i]}"
}

df_free_bytes() { df -B1 "$HOME" | awk 'NR==2{print $4}'; }

pre_free="$(df_free_bytes)"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$REPORT"; }

safe_rm() {
  local p="$1"
  # 安全保護：避免刪除 /、$HOME
  [[ -z "$p" ]] && return 0
  [[ "$p" = "/" ]] && return 0
  [[ "$p" = "$HOME" ]] && return 0
  if [[ "$DRY_RUN" = "1" ]]; then
    echo "$p" >> "$CANDIDATE_LIST"
    return 0
  else
    # 記錄大小
    if [ -e "$p" ]; then
      local sz
      sz=$(du -sb --apparent-size "$p" 2>>"$ERR_LOG" | awk '{print $1}')
      echo "$p" >> "$DELETED_LIST"
      rm -rf --one-file-system "$p" 2>>"$ERR_LOG" || true
      echo "$sz"
    fi
  fi
}

sum_deleted=0

delete_many() {
  # 讀取 find 產生的 NUL 分隔清單，逐一刪除並累計大小
  local total=0 p
  while IFS= read -r -d '' p; do
    sz=$(safe_rm "$p" || echo 0)
    [[ -n "$sz" ]] && total=$((total + sz))
  done
  echo "$total"
}

log "Roots: $ROOTS"
log "LOG_OLDER_THAN_DAYS=$LOG_OLDER_THAN_DAYS ALLOW_NODE=$ALLOW_NODE ALLOW_APT=$ALLOW_APT DRY_RUN=$DRY_RUN"
log "Report dir: $OUTDIR"
echo > "$DELETED_LIST"; echo > "$CANDIDATE_LIST"

# ========== 1) 快取/生成物/建置產物/暫存備份 ==========
log "掃描並清理：__pycache__、.pytest_cache、.mypy_cache、.ruff_cache、.ipynb_checkpoints、.cache、dist、build…"
mapfile -t roots <<< "$ROOTS"

# 1.a 目錄類型（直接移除整個資料夾）
for pat in "__pycache__" ".pytest_cache" ".mypy_cache" ".ruff_cache" ".ipynb_checkpoints" "dist" "build"; do
  while IFS= read -r -d '' d; do
    sz=$(safe_rm "$d" || echo 0); [[ -n "$sz" ]] && sum_deleted=$((sum_deleted + sz))
  done < <(find "${roots[@]}" -xdev -type d -name "$pat" -prune -print0 2>>"$ERR_LOG")
done

# 1.b .cache 比較大，拆開處理：僅刪子項目（避免直接刪 HOME/.cache 本身失敗）
while IFS= read -r -d '' d; do
  if [[ "$DRY_RUN" = "1" ]]; then
    echo "$d" >> "$CANDIDATE_LIST"
  else
    while IFS= read -r -d '' sub; do
      sz=$(safe_rm "$sub" || echo 0); [[ -n "$sz" ]] && sum_deleted=$((sum_deleted + sz))
    done < <(find "$d" -mindepth 1 -maxdepth 1 -print0 2>>"$ERR_LOG")
  fi
done < <(find "${roots[@]}" -xdev -type d -name ".cache" -print0 2>>"$ERR_LOG")

# 1.c 暫存/備份檔
log "清理：*.tmp *.temp *.bak *~"
while IFS= read -r -d '' f; do
  sz=$(safe_rm "$f" || echo 0); [[ -n "$sz" ]] && sum_deleted=$((sum_deleted + sz))
done < <(find "${roots[@]}" -xdev -type f \( -name "*.tmp" -o -name "*.temp" -o -name "*.bak" -o -name "*~" \) -print0 2>>"$ERR_LOG")

# 1.d 舊 log（> LOG_OLDER_THAN_DAYS）
log "清理：舊 log (*.log, > ${LOG_OLDER_THAN_DAYS} 天)"
while IFS= read -r -d '' f; do
  sz=$(safe_rm "$f" || echo 0); [[ -n "$sz" ]] && sum_deleted=$((sum_deleted + sz))
done < <(find "${roots[@]}" -xdev -type f -name "*.log" -mtime +"$LOG_OLDER_THAN_DAYS" -print0 2>>"$ERR_LOG")

# ========== 2) 壓縮檔旁已有同名資料夾 → 刪壓縮檔 ==========
log "清理：旁邊已有同名資料夾的壓縮檔（zip/rar/7z/tar.gz/tgz/tar.bz2/tar.xz/zst）"
strip_ext() {
  local f="$1" base="$f"
  base="${base%.tar.gz}"; base="${base%.tgz}"; base="${base%.tar.bz2}"; base="${base%.tar.xz}"
  base="${base%.zip}"; base="${base%.rar}"; base="${base%.7z}"; base="${base%.zst}"; base="${base%.gz}"
  echo "$base"
}
while IFS= read -r -d '' f; do
  dir_base="$(strip_ext "$f")"
  dir_name="$(basename "$dir_base")"
  parent="$(dirname "$f")"
  if [[ -d "$parent/$dir_name" ]]; then
    sz=$(safe_rm "$f" || echo 0); [[ -n "$sz" ]] && sum_deleted=$((sum_deleted + sz))
  fi
done < <(find "${roots[@]}" -xdev -type f \( -name "*.zip" -o -name "*.rar" -o -name "*.7z" -o -name "*.tar.gz" -o -name "*.tgz" -o -name "*.tar.bz2" -o -name "*.tar.xz" -o -name "*.zst" -o -name "*.gz" \) -print0 2>>"$ERR_LOG")

# ========== 3) 可選：node_modules ==========
if [[ "$ALLOW_NODE" = "1" ]]; then
  log "允許清理 node_modules/（可能很大，移除後需 npm/yarn 重新安裝）"
  while IFS= read -r -d '' d; do
    sz=$(safe_rm "$d" || echo 0); [[ -n "$sz" ]] && sum_deleted=$((sum_deleted + sz))
  done < <(find "${roots[@]}" -xdev -type d -name "node_modules" -prune -print0 2>>"$ERR_LOG")
else
  log "略過 node_modules/（設定 ALLOW_NODE=1 可啟用移除）"
fi

# ========== 4) 可選：APT 快取 ==========
if [[ "$ALLOW_APT" = "1" ]]; then
  log "允許清理 APT 快取（需要 sudo）"
  if command -v sudo >/dev/null 2>&1; then
    if [[ "$DRY_RUN" = "1" ]]; then
      echo "[DRY_RUN] sudo apt-get clean / sudo rm -rf /var/cache/apt/archives/*" >> "$CANDIDATE_LIST"
    else
      { sudo apt-get clean && sudo rm -rf /var/cache/apt/archives/*; } 2>>"$ERR_LOG" || true
    fi
  else
    log "未找到 sudo，略過 APT 清理"
  fi
else
  log "略過 APT 快取清理（設定 ALLOW_APT=1 可啟用）"
fi

post_free="$(df_free_bytes)"
freed=$(( post_free - pre_free ))  # 正值代表剩餘空間增加（可能為負，取 0）
[[ $freed -lt 0 ]] && freed=0

log "----------------------------------------"
log "刪除項目數：$(wc -l < "$DELETED_LIST" 2>/dev/null || echo 0)"
log "實際刪除容量（估算，檔案大小加總）：$(human "$sum_deleted")"
log "磁碟可用空間增加：$(human "$freed")"
log "候選清單（DRY_RUN=1 時有效）：$CANDIDATE_LIST"
log "詳細刪除清單：$DELETED_LIST"
log "錯誤與跳過紀錄：$ERR_LOG"
log "報告：$REPORT"

# 嘗試在 Windows 檔案總管開啟報告資料夾（WSL）
if command -v wslpath >/dev/null 2>&1 && command -v explorer.exe >/dev/null 2>&1; then
  explorer.exe "$(wslpath -w "$OUTDIR")" >/dev/null 2>&1 || true
fi

