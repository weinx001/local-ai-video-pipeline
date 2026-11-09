#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || {
  echo "Usage: check_job.sh <job-name>" >&2
  exit 2
}

name="$1"
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "invalid job-name" >&2
  exit 2
}

root="$(cd "$(dirname "$0")/.." && pwd)"
jobs_dir="${XIYOU_JOBS_DIR:-$root/work/jobs}"
log_file="$jobs_dir/$name.log"
pid_file="$jobs_dir/$name.pid"
exit_file="$jobs_dir/$name.exit"

[[ -f "$log_file" ]] || {
  echo "job not found: $name" >&2
  exit 4
}

status="unknown"
pid=""
if [[ -f "$exit_file" ]]; then
  status="exited"
elif [[ -f "$pid_file" ]]; then
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    status="running"
  fi
fi

printf 'job=%s\nstatus=%s\npid=%s\nlog=%s\n' "$name" "$status" "$pid" "$log_file"
if [[ -f "$exit_file" ]]; then
  printf 'exit_code=%s\n' "$(cat "$exit_file")"
fi
printf '%s\n' '--- log tail ---'
tail -c 16000 "$log_file" | tail -n 40
