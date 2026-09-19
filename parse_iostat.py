#!/usr/bin/env python3

import argparse
import csv
import math
import os
import statistics
from collections import defaultdict


def _f(value):
    try:
        return float(value.replace(',', '.'))
    except (AttributeError, ValueError):
        return None


def _mean(values):
    vals = [v for v in values if v is not None and math.isfinite(v)]
    return statistics.fmean(vals) if vals else None


def _norm_dev(dev):
    return os.path.basename(dev.rstrip('/'))


def parse_diskstats(path):
    out = {}
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            cols = raw.split()
            if len(cols) < 14:
                continue
            dev = cols[2]
            try:
                out[dev] = {
                    'read_sectors': int(cols[5]),
                    'write_sectors': int(cols[9]),
                }
            except ValueError:
                continue
    return out


def parse_iostat(path, wanted_devices=None):
    """Parse text output of `iostat -x -m` without assuming column positions.

    Works with both older sysstat layouts (rMB/s, wMB/s, avgrq-sz,
    avgqu-sz, ...) and newer layouts (rMB/s, rareq-sz, wMB/s,
    wareq-sz, aqu-sz, ...), because every report is decoded from its
    Device header.
    """
    wanted = None
    if wanted_devices:
        wanted = {_norm_dev(d) for d in wanted_devices}

    records = defaultdict(list)
    header = None

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            toks = line.replace(',', '.').split()
            if not toks:
                continue

            first = toks[0].rstrip(':')
            if first == 'Device':
                header = [h.rstrip(':') for h in toks[1:]]
                continue

            if header is None:
                continue

            dev = _norm_dev(toks[0])
            if wanted is not None and dev not in wanted:
                continue

            vals = toks[1:]
            if len(vals) < len(header):
                continue

            row = {}
            ok = True
            for key, value in zip(header, vals):
                fv = _f(value)
                if fv is None:
                    ok = False
                    break
                row[key] = fv
            if ok:
                records[dev].append(row)

    return records


def _metric(row, *names):
    for name in names:
        if name in row:
            return row[name]
    return None


def read_mb_s(row):
    v = _metric(row, 'rMB/s')
    if v is not None:
        return v
    v = _metric(row, 'rkB/s', 'rKB/s')
    if v is not None:
        return v / 1024.0
    return None


def write_mb_s(row):
    v = _metric(row, 'wMB/s')
    if v is not None:
        return v
    v = _metric(row, 'wkB/s', 'wKB/s')
    if v is not None:
        return v / 1024.0
    return None


def summarize_records(records):
    summary = {}
    for dev, rows in records.items():
        rmb = [read_mb_s(r) for r in rows]
        wmb = [write_mb_s(r) for r in rows]
        util = [_metric(r, '%util') for r in rows]
        qsz = [_metric(r, 'aqu-sz', 'avgqu-sz') for r in rows]
        rawait = [_metric(r, 'r_await', 'await') for r in rows]
        wawait = [_metric(r, 'w_await', 'await') for r in rows]

        # Newer sysstat reports read/write request sizes separately in kB.
        # Older sysstat reports avgrq-sz in 512-byte sectors. Convert the
        # legacy value to KiB so the result has one consistent unit.
        rreq = []
        wreq = []
        for r in rows:
            rv = _metric(r, 'rareq-sz')
            wv = _metric(r, 'wareq-sz')
            if rv is None and 'avgrq-sz' in r:
                rv = r['avgrq-sz'] * 0.5
            if wv is None and 'avgrq-sz' in r:
                wv = r['avgrq-sz'] * 0.5
            rreq.append(rv)
            wreq.append(wv)

        summary[dev] = {
            'IOSTAT_SAMPLES': len(rows),
            'AVG_READ_MB_PER_SEC': _mean(rmb),
            'AVG_WRITE_MB_PER_SEC': _mean(wmb),
            'AVG_QUEUE_SIZE': _mean(qsz),
            'AVG_READ_AWAIT_MS': _mean(rawait),
            'AVG_WRITE_AWAIT_MS': _mean(wawait),
            'AVG_READ_REQ_KIB': _mean(rreq),
            'AVG_WRITE_REQ_KIB': _mean(wreq),
            'AVG_DEV_UTIL_PCT': _mean(util),
        }
    return summary


def main():
    ap = argparse.ArgumentParser(description='Robust iostat and /proc/diskstats parser')
    ap.add_argument('--iostat', required=True)
    ap.add_argument('--before', required=True)
    ap.add_argument('--after', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--device', action='append', required=True,
                    help='Device name, e.g. nvme0n1; may be repeated')
    args = ap.parse_args()

    devices = [_norm_dev(d) for d in args.device]
    before = parse_diskstats(args.before)
    after = parse_diskstats(args.after)
    records = parse_iostat(args.iostat, devices)
    summary = summarize_records(records)

    rows = []
    for dev in devices:
        if dev in before and dev in after:
            read_sectors = after[dev]['read_sectors'] - before[dev]['read_sectors']
            write_sectors = after[dev]['write_sectors'] - before[dev]['write_sectors']
            if read_sectors < 0 or write_sectors < 0:
                raise RuntimeError(f'diskstats counter went backwards for {dev}')
            read_bytes = read_sectors * 512
            write_bytes = write_sectors * 512
            totals = {
                'TOTAL_READ_BYTES': read_bytes,
                'TOTAL_WRITE_BYTES': write_bytes,
                'TOTAL_READ_MIB': read_bytes / (1024.0 ** 2),
                'TOTAL_WRITE_MIB': write_bytes / (1024.0 ** 2),
                'TOTAL_READ_GIB': read_bytes / (1024.0 ** 3),
                'TOTAL_WRITE_GIB': write_bytes / (1024.0 ** 3),
            }
            for k, v in totals.items():
                rows.append((dev, k, v))
        else:
            missing = []
            if dev not in before:
                missing.append('before')
            if dev not in after:
                missing.append('after')
            print(f'WARNING: {dev} absent from diskstats {"/".join(missing)} snapshot', flush=True)

        if dev not in summary:
            print(f'WARNING: no iostat samples found for {dev}', flush=True)
            continue
        for k, v in summary[dev].items():
            if v is not None:
                rows.append((dev, k, v))

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['DEVICE', 'METRIC', 'VALUE'])
        for dev, metric, value in rows:
            if isinstance(value, float):
                w.writerow([dev, metric, f'{value:.9f}'])
            else:
                w.writerow([dev, metric, value])


if __name__ == '__main__':
    main()
