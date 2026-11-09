#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: run_job_background.sh <job-name> -- <command> [args...]

Starts one long-running project job in the background and returns immediately.
Only one background project job may run at a time.
EOF
  exit 2
}

[[ $# -ge 2 && "$2" == "--" ]] || usage

name="$1"
shift 2
[[ $# -ge 1 ]] || usage
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "job-name may only contain letters, numbers, dot, underscore and dash" >&2
  exit 2
}

root="$(cd "$(dirname "$0")/.." && pwd)"
jobs_dir="${XIYOU_JOBS_DIR:-$root/work/jobs}"
mkdir -p "$jobs_dir"

lock_dir="$jobs_dir/.active.lock"
pid_file="$jobs_dir/$name.pid"
exit_file="$jobs_dir/$name.exit"
log_file="$jobs_dir/$name.log"

if [[ -d "$lock_dir" ]]; then
  previous_pid="$(cat "$lock_dir/pid" 2>/dev/null || true)"
  if [[ -n "$previous_pid" ]] && kill -0 "$previous_pid" 2>/dev/null; then
    echo "another background project job is running: pid=$previous_pid" >&2
    exit 3
  fi
  if [[ -f "$lock_dir/starting" ]] && [[ -z "$(find "$lock_dir/starting" -mmin +1 -print -quit 2>/dev/null)" ]]; then
    echo "another background project job is still starting; retry shortly" >&2
    exit 3
  fi
  unlink "$lock_dir/starting" 2>/dev/null || true
  unlink "$lock_dir/pid" 2>/dev/null || true
  rmdir "$lock_dir" 2>/dev/null || {
    echo "stale job lock could not be cleared: $lock_dir" >&2
    exit 3
  }
fi

mkdir "$lock_dir"
printf '%s\n' "starting" > "$lock_dir/starting"
unlink "$exit_file" 2>/dev/null || true

export XIYOU_LOCK_DIR="$lock_dir"
export XIYOU_PID_FILE="$pid_file"
export XIYOU_EXIT_FILE="$exit_file"

cd "$root"
nohup bash -c '
  set -euo pipefail
  printf "%s\n" "$$" > "$XIYOU_LOCK_DIR/pid"
  printf "%s\n" "$$" > "$XIYOU_PID_FILE"
  unlink "$XIYOU_LOCK_DIR/starting" 2>/dev/null || true
  finish() {
    status=$?
    trap - EXIT
    printf "%s\n" "$status" > "$XIYOU_EXIT_FILE"
    unlink "$XIYOU_PID_FILE" 2>/dev/null || true
    unlink "$XIYOU_LOCK_DIR/starting" 2>/dev/null || true
    unlink "$XIYOU_LOCK_DIR/pid" 2>/dev/null || true
    rmdir "$XIYOU_LOCK_DIR" 2>/dev/null || true
    exit "$status"
  }
  trap finish EXIT
  "$@"
' _ "$@" >"$log_file" 2>&1 </dev/null &

launcher_pid=$!
printf 'job=%s\nlauncher_pid=%s\nlog=%s\n' "$name" "$launcher_pid" "$log_file"
