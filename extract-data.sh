#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 -r RESULT_DIR -d DEVICE [-d DEVICE ...]

Options:
  -r  Directory with raw statistics
  -d  Block device to summarize; may be repeated
  -h  Show this help
EOF
  exit 1
}

RESULT_DIR=""
DEVICES=()
while getopts ":r:d:h" opt; do
  case "${opt}" in
    r) RESULT_DIR="${OPTARG}" ;;
    d) DEVICES+=("${OPTARG}") ;;
    h) usage ;;
    *) usage ;;
  esac
done
[[ -n "${RESULT_DIR}" ]] || usage
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

python3 "${SCRIPT_DIR}/parse_system_stats.py" \
  --result-dir "${RESULT_DIR}" \
  --output "${RESULT_DIR}/system.csv"

# Prefer the new deterministic names, but accept historical result directories.
IOSTAT="${RESULT_DIR}/iostat.txt"
BEFORE="${RESULT_DIR}/diskstats.before"
AFTER="${RESULT_DIR}/diskstats.after"

if [[ ! -f "${IOSTAT}" ]]; then
  IOSTAT=$(find "${RESULT_DIR}" -maxdepth 1 -type f -name 'iostat-*' | sort | tail -n1)
fi
if [[ ! -f "${BEFORE}" ]]; then
  BEFORE=$(find "${RESULT_DIR}" -maxdepth 1 -type f -name 'diskstats-before-*' | sort | tail -n1)
fi
if [[ ! -f "${AFTER}" ]]; then
  AFTER=$(find "${RESULT_DIR}" -maxdepth 1 -type f -name 'diskstats-after-*' | sort | tail -n1)
fi

if (( ${#DEVICES[@]} > 0 )) && [[ -n "${IOSTAT:-}" && -f "${IOSTAT}" && -n "${BEFORE:-}" && -f "${BEFORE}" && -n "${AFTER:-}" && -f "${AFTER}" ]]; then
  disk_args=(-b "${BEFORE}" -a "${AFTER}" -s "${IOSTAT}" -r "${RESULT_DIR}")
  for dev in "${DEVICES[@]}"; do
    disk_args+=(-d "${dev}")
  done
  "${SCRIPT_DIR}/disk_util.sh" "${disk_args[@]}"
else
  echo "WARNING: disk statistics are incomplete; skipping disk summary" >&2
fi

# Plot memory if a compatible trace is present.
if [[ -f "${RESULT_DIR}/mem_usage.txt" ]]; then
  python3 "${SCRIPT_DIR}/plot_memusage.py" \
    -i "${RESULT_DIR}/mem_usage.txt" \
    -o "${RESULT_DIR}/plots/mem_usage.png" || true
fi
