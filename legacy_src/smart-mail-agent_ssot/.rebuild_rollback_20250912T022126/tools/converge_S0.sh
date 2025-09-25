#!/usr/bin/env bash
set -Eeuo pipefail
PROJ="${PROJ:-$(pwd)}"; cd "$PROJ"
ts() { date +%Y%m%dT%H%M%S; }; TS="$(ts)"
echo "[S0] converge start @ $TS"

mkdir -p legacy legacy/db legacy/artifacts legacy/99_snapshot reports_auto/status db
MAIN="db/sma.sqlite"; touch "$MAIN"

# 扁平化 artifacts_prod/artifacts_prod -> artifacts_prod
if [ -d artifacts_prod/artifacts_prod ]; then
  echo "[S0-2] flatten artifacts_prod/"
  shopt -s nullglob
  for f in artifacts_prod/artifacts_prod/*; do
    base="$(basename "$f")"
    [ -e "artifacts_prod/$base" ] && cp -a "artifacts_prod/$base" "legacy/artifacts/${base}.bak.$TS" || true
    mv -f "$f" "artifacts_prod/"
  done
  rmdir artifacts_prod/artifacts_prod || true
fi

# 合併可能的舊 DB（僅做 INSERT/IGNORE，永不 DROP）
merge_db () {
  local OLD="$1"; [ -f "$OLD" ] || return 0
  echo "  - merging $OLD → $MAIN"
  mapfile -t tables < <(sqlite3 "$OLD" "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
  [ "${#tables[@]}" -eq 0 ] && { echo "    (no tables)"; return 0; }
  get_cols () { sqlite3 "$1" "PRAGMA table_info('$2');" | awk -F'|' '{print $2}'; }

  SQL="$(mktemp)"; : >"$SQL"
  { echo "ATTACH '$OLD' AS old;"; echo "BEGIN;"; } >> "$SQL"

  for t in "${tables[@]}"; do
    mc="$(get_cols "$MAIN" "$t")"
    oc="$(get_cols "$OLD"  "$t")"
    if [ -z "$mc" ] && [ -n "$oc" ]; then
      echo "CREATE TABLE IF NOT EXISTS \"$t\" AS SELECT * FROM old.\"$t\" WHERE 0;" >> "$SQL"
      cols="$(printf "%s\n" "$oc" | paste -sd, -)"
      echo "INSERT OR IGNORE INTO \"$t\" ($cols) SELECT $cols FROM old.\"$t\";" >> "$SQL"
    else
      inter="$(comm -12 <(printf "%s\n" "$mc" | sort -u) <(printf "%s\n" "$oc" | sort -u))"
      if [ -z "$inter" ] && [ -n "$oc" ] && [ -n "$mc" ]; then
        missing="$(comm -23 <(printf "%s\n" "$oc" | sort -u) <(printf "%s\n" "$mc" | sort -u))"
        while IFS= read -r col; do
          [ -z "$col" ] && continue
          echo "ALTER TABLE \"$t\" ADD COLUMN \"$col\" TEXT;" >> "$SQL"
        done <<< "$missing"
        use="$(printf "%s\n" "$oc" | paste -sd, -)"
        echo "INSERT OR IGNORE INTO \"$t\" ($use) SELECT $use FROM old.\"$t\";" >> "$SQL"
      else
        use="$(printf "%s\n" "$inter" | paste -sd, -)"
        [ -z "$use" ] || echo "INSERT OR IGNORE INTO \"$t\" ($use) SELECT $use FROM old.\"$t\";" >> "$SQL"
      fi
    fi
  done

  { echo "COMMIT;"; echo "DETACH old;"; } >> "$SQL"
  sqlite3 "$MAIN" < "$SQL"
  rm -f "$SQL"
  dest="legacy/db/$(basename "$OLD").$TS"; mv -f "$OLD" "$dest" || true
  echo "    archived -> $dest"
}

for olddb in data/stats.db db/records.db reports_auto/audit.sqlite3; do
  [ -f "$olddb" ] && merge_db "$olddb" || true
done

# 自我遷移：只增不刪
python - "$MAIN" <<'PY'
import sqlite3,sys
db=sys.argv[1]
conn=sqlite3.connect(db);cur=conn.cursor()
def cols(t):
    try: return [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
    except: return []
cur.execute("""CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY, case_id TEXT, action_type TEXT, path TEXT, created_at TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS intent_preds (
  case_id TEXT PRIMARY KEY, label TEXT
)""")
for t,c,ddl in [
    ("intent_preds","confidence","REAL"),
    ("intent_preds","created_at","TEXT"),
    ("kie_spans","case_id","TEXT"),
    ("kie_spans","key","TEXT"),
    ("kie_spans","value","TEXT"),
    ("kie_spans","start","INT"),
    ("kie_spans","end","INT"),
    ("err_log","ts","TEXT"),
    ("err_log","case_id","TEXT"),
    ("err_log","err","TEXT"),
]:
    if cols(t) and c not in cols(t):
        cur.execute(f'ALTER TABLE "{t}" ADD COLUMN "{c}" {ddl}')
conn.commit(); conn.close()
PY

echo "[S0] converge done."
