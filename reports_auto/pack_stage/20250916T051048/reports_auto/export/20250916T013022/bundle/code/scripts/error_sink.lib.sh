# error_sink.lib.sh
: "${SMA_ERROR_SINK:=reports_auto/ERR}"
error_sink::init(){ mkdir -p "$SMA_ERROR_SINK"; }
error_sink::copy(){ local src="$1" dst="$2"; [ -n "${src:-}" ] && [ -f "$src" ] && cp -f "$src" "$dst" 2>/dev/null || true; }
sink_err(){ # sink_err <run_dir> <err_file> <py_last> [server_log]
  local d="$1" e="$2" py="$3" slog="${4:-}"
  error_sink::init
  error_sink::copy "$e"        "$SMA_ERROR_SINK/api.err"
  error_sink::copy "$d/run.log" "$SMA_ERROR_SINK/run.log"
  error_sink::copy "$slog"     "$SMA_ERROR_SINK/server.log"
  error_sink::copy "$py"       "$SMA_ERROR_SINK/py_last_trace.txt"
  { echo "RUN_DIR=$(cd "$d" && pwd)"; } > "$SMA_ERROR_SINK/where.txt"
  ln -sfn "$(cd "$d"&&pwd)" "$SMA_ERROR_SINK/LATEST_RUN" 2>/dev/null || true
}
sink_run(){ # on successful/normal exit 也更新固定路徑（不覆蓋 api.err）
  local d="$1"
  error_sink::init
  error_sink::copy "$d/run.log" "$SMA_ERROR_SINK/run.log"
  { echo "RUN_DIR=$(cd "$d" && pwd)"; } > "$SMA_ERROR_SINK/where.txt"
  ln -sfn "$(cd "$d"&&pwd)" "$SMA_ERROR_SINK/LATEST_RUN" 2>/dev/null || true
}
