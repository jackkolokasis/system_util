#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 -b DISKSTATS_BEFORE -a DISKSTATS_AFTER -s IOSTAT -r RESULT_DIR -d DEVICE [-d DEVICE ...]
EOF
  exit 1
}

DSTATS_BEFORE=""
DSTATS_AFTER=""
IOSTAT=""
RESULT_DIR=""
DEVICES=()
while getopts ":b:a:s:r:d:h" opt; do
  case "${opt}" in
    b) DSTATS_BEFORE="${OPTARG}" ;;
    a) DSTATS_AFTER="${OPTARG}" ;;
    s) IOSTAT="${OPTARG}" ;;
    r) RESULT_DIR="${OPTARG}" ;;
    d) DEVICES+=("${OPTARG}") ;;
    h) usage ;;
    *) usage ;;
  esac
done

[[ -n "${DSTATS_BEFORE}" && -n "${DSTATS_AFTER}" && -n "${IOSTAT}" && -n "${RESULT_DIR}" ]] || usage
(( ${#DEVICES[@]} > 0 )) || usage

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "${RESULT_DIR}/plots"

args=(
  --iostat "${IOSTAT}"
  --before "${DSTATS_BEFORE}"
  --after "${DSTATS_AFTER}"
  --output "${RESULT_DIR}/diskstat.csv"
)
plot_args=(-i "${IOSTAT}" -o "${RESULT_DIR}/plots")
for dev in "${DEVICES[@]}"; do
  args+=(--device "${dev}")
  plot_args+=(-s "${dev}")
done

python3 "${SCRIPT_DIR}/parse_iostat.py" "${args[@]}"
python3 "${SCRIPT_DIR}/plot_iostat.py" "${plot_args[@]}"
