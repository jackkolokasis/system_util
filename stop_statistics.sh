#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 -d RESULT_DIR [-g CGROUP_NAME]

Options:
  -d  Directory containing statistics for the current run
  -g  Cgroup name/path below /sys/fs/cgroup (default: read from metadata, else memlim)
  -h  Show this help
EOF
  exit 1
}

RESULT_DIR=""
CGROUP_NAME=""
while getopts ":d:g:h" opt; do
  case "${opt}" in
    d) RESULT_DIR="${OPTARG}" ;;
    g) CGROUP_NAME="${OPTARG}" ;;
    h) usage ;;
    *) usage ;;
  esac
done
[[ -n "${RESULT_DIR}" ]] || usage

if [[ -z "${CGROUP_NAME}" && -f "${RESULT_DIR}/stats_metadata.env" ]]; then
  CGROUP_NAME=$(awk -F= '$1=="CGROUP_NAME" {print substr($0,index($0,"=")+1)}' "${RESULT_DIR}/stats_metadata.env" | tail -n1)
fi
CGROUP_NAME=${CGROUP_NAME:-memlim}
CGROUP_PATH="/sys/fs/cgroup/${CGROUP_NAME#/}"

# Stop only the monitoring processes started by this run. Never use killall,
# because that can terminate unrelated experiments/users' iostat/mpstat jobs.
stop_pidfile() {
  local pidfile="$1"
  [[ -f "${pidfile}" ]] || return 0
  local pid
  pid=$(cat "${pidfile}" 2>/dev/null || true)
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill -INT "${pid}" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.1
    done
    kill -TERM "${pid}" 2>/dev/null || true
  fi
}

stop_pidfile "${RESULT_DIR}/iostat.pid"
stop_pidfile "${RESULT_DIR}/mpstat.pid"
stop_pidfile "${RESULT_DIR}/cgroup_cpu.pid"

# Capture final counters synchronously, after the benchmark and before the
# cgroup is deleted by run.sh.
cat /proc/diskstats > "${RESULT_DIR}/diskstats.after"
if [[ -r "${CGROUP_PATH}/cpu.stat" ]]; then
  cat "${CGROUP_PATH}/cpu.stat" > "${RESULT_DIR}/cgroup_cpu.after"
fi

END_NS=$(date +%s%N)
printf '%s\n' "${END_NS}" > "${RESULT_DIR}/stats_end_ns"
date --iso-8601=ns >> "${RESULT_DIR}/parsedate"
