#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 OUTPUT CGROUP_NAME [INTERVAL_S]" >&2
  exit 1
fi

OUTPUT=$1
CGROUP_NAME=$2
INTERVAL=${3:-1}
CGROUP_PATH="/sys/fs/cgroup/${CGROUP_NAME#/}"
STAT="${CGROUP_PATH}/memory.stat"

[[ -r "${STAT}" ]] || { echo "ERROR: cannot read ${STAT}" >&2; exit 1; }

while true; do
  # Select by key rather than assuming anon/file are the first two lines.
  awk '$1 == "anon" || $1 == "file" {print $1, $2}' "${STAT}" >> "${OUTPUT}"
  sleep "${INTERVAL}"
done
