#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 -d RESULT_DIR [-g CGROUP_NAME] [-c ALLOCATED_CORES] [-i INTERVAL]

Options:
  -d  Directory where statistics are written
  -g  Cgroup name/path below /sys/fs/cgroup (default: memlim)
  -c  Total Spark executor cores for this run. Used to normalize CPU utilization.
      Defaults to all online host CPUs for backward compatibility.
  -i  Sampling interval in seconds (default: 1)
  -h  Show this help
EOF
  exit 1
}

RESULT_DIR=""
CGROUP_NAME="memlim"
ALLOCATED_CORES=""
INTERVAL=1

while getopts ":d:g:c:i:h" opt; do
  case "${opt}" in
    d) RESULT_DIR="${OPTARG}" ;;
    g) CGROUP_NAME="${OPTARG}" ;;
    c) ALLOCATED_CORES="${OPTARG}" ;;
    i) INTERVAL="${OPTARG}" ;;
    h) usage ;;
    *) usage ;;
  esac
done

[[ -n "${RESULT_DIR}" ]] || usage
command -v iostat >/dev/null 2>&1 || { echo "ERROR: iostat not found (install sysstat)" >&2; exit 1; }
command -v mpstat >/dev/null 2>&1 || { echo "ERROR: mpstat not found (install sysstat)" >&2; exit 1; }

mkdir -p "${RESULT_DIR}"
HOST_ONLINE_CPUS=$(nproc)
ALLOCATED_CORES=${ALLOCATED_CORES:-${HOST_ONLINE_CPUS}}
CGROUP_PATH="/sys/fs/cgroup/${CGROUP_NAME#/}"

START_NS=$(date +%s%N)
printf '%s\n' "${START_NS}" > "${RESULT_DIR}/stats_start_ns"
date --iso-8601=ns > "${RESULT_DIR}/parsedate"

# Record enough metadata to make later parsing reproducible.
{
  echo "ALLOCATED_CORES=${ALLOCATED_CORES}"
  echo "HOST_ONLINE_CPUS=${HOST_ONLINE_CPUS}"
  echo "CGROUP_NAME=${CGROUP_NAME}"
  echo "CGROUP_PATH=${CGROUP_PATH}"
  echo "SAMPLE_INTERVAL_S=${INTERVAL}"
  echo "KERNEL=$(uname -r)"
  echo "IOSTAT_VERSION=$(iostat -V 2>&1 | head -n 1 | tr ' ' '_')"
  echo "MPSTAT_VERSION=$(mpstat -V 2>&1 | head -n 1 | tr ' ' '_')"
} > "${RESULT_DIR}/stats_metadata.env"

# Synchronous snapshots avoid races with very short experiments.
cat /proc/diskstats > "${RESULT_DIR}/diskstats.before"
if [[ -r "${CGROUP_PATH}/cpu.stat" ]]; then
  cat "${CGROUP_PATH}/cpu.stat" > "${RESULT_DIR}/cgroup_cpu.before"
else
  echo "WARNING: ${CGROUP_PATH}/cpu.stat is unavailable; CPU accounting will fall back to host mpstat." >&2
fi

# Force a stable locale so decimal separators and column names do not depend on
# the machine locale. -y skips the first iostat report, which otherwise covers
# time since boot rather than the benchmark interval.
LC_ALL=C iostat -x -m -y "${INTERVAL}" > "${RESULT_DIR}/iostat.txt" 2>&1 &
echo $! > "${RESULT_DIR}/iostat.pid"

LC_ALL=C mpstat -P ALL "${INTERVAL}" > "${RESULT_DIR}/mpstat.txt" 2>&1 &
echo $! > "${RESULT_DIR}/mpstat.pid"

# Optional time series of cgroup CPU counters. Aggregate CPU time is computed
# from the before/after snapshots, so losing one sample does not affect totals.
if [[ -r "${CGROUP_PATH}/cpu.stat" ]]; then
  (
    echo "timestamp_ns,usage_usec,user_usec,system_usec"
    while true; do
      ts=$(date +%s%N)
      usage=$(awk '$1=="usage_usec" {print $2}' "${CGROUP_PATH}/cpu.stat")
      user=$(awk '$1=="user_usec" {print $2}' "${CGROUP_PATH}/cpu.stat")
      system=$(awk '$1=="system_usec" {print $2}' "${CGROUP_PATH}/cpu.stat")
      printf '%s,%s,%s,%s\n' "${ts}" "${usage:-0}" "${user:-0}" "${system:-0}"
      sleep "${INTERVAL}"
    done
  ) > "${RESULT_DIR}/cgroup_cpu.csv" &
  echo $! > "${RESULT_DIR}/cgroup_cpu.pid"
fi
