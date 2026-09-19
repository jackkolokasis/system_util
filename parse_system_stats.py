#!/usr/bin/env python3

import argparse
import csv
import glob
import os
import statistics


def parse_env(path):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def parse_kv(path):
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            p = raw.split()
            if len(p) >= 2:
                try:
                    data[p[0]] = int(p[1])
                except ValueError:
                    pass
    return data


def parse_mpstat(path):
    """Parse mpstat -P ALL output using the header, not fixed columns."""
    samples = []
    header = None
    if not path or not os.path.exists(path):
        return {}

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip().replace(',', '.')
            if not line:
                continue
            toks = line.split()
            if 'CPU' in toks and '%idle' in toks:
                i = toks.index('CPU')
                header = toks[i + 1:]
                continue
            if header is None:
                continue
            if toks[0].startswith('Average:'):
                continue
            try:
                i = toks.index('all')
            except ValueError:
                continue
            vals = toks[i + 1:i + 1 + len(header)]
            if len(vals) != len(header):
                continue
            row = {}
            try:
                for k, v in zip(header, vals):
                    row[k] = float(v)
            except ValueError:
                continue
            samples.append(row)

    if not samples:
        return {}

    def avg(*names):
        vals = []
        for r in samples:
            for name in names:
                if name in r:
                    vals.append(r[name])
                    break
        return statistics.fmean(vals) if vals else None

    usr = avg('%usr', '%user')
    sys = avg('%sys', '%system')
    iow = avg('%iowait')
    idle = avg('%idle')
    return {
        'HOST_USR_UTIL(%)': usr,
        'HOST_SYS_UTIL(%)': sys,
        'HOST_IOW_UTIL(%)': iow,
        'HOST_IDLE_UTIL(%)': idle,
        'HOST_CPU_UTIL(%)': None if idle is None else 100.0 - idle,
        'MPSTAT_SAMPLES': len(samples),
    }


def metric_rows(result_dir):
    meta = parse_env(os.path.join(result_dir, 'stats_metadata.env'))

    mpstat_path = os.path.join(result_dir, 'mpstat.txt')
    if not os.path.exists(mpstat_path):
        matches = sorted(glob.glob(os.path.join(result_dir, 'mpstat-*')))
        mpstat_path = matches[-1] if matches else ''
    host = parse_mpstat(mpstat_path)

    allocated = int(meta.get('ALLOCATED_CORES', '0') or 0)
    host_cpus = int(meta.get('HOST_ONLINE_CPUS', '0') or 0)

    try:
        start_ns = int(open(os.path.join(result_dir, 'stats_start_ns')).read().strip())
        end_ns = int(open(os.path.join(result_dir, 'stats_end_ns')).read().strip())
        duration_s = max(0.0, (end_ns - start_ns) / 1e9)
    except (OSError, ValueError):
        duration_s = 0.0

    before = parse_kv(os.path.join(result_dir, 'cgroup_cpu.before'))
    after = parse_kv(os.path.join(result_dir, 'cgroup_cpu.after'))

    rows = []
    rows.append(('MEASUREMENT_DURATION_S', duration_s))
    rows.append(('ALLOCATED_CORES', allocated))
    rows.append(('HOST_ONLINE_CPUS', host_cpus))

    have_cgroup = all(k in before and k in after for k in ('usage_usec', 'user_usec', 'system_usec'))
    if have_cgroup:
        du = max(0, after['usage_usec'] - before['usage_usec'])
        du_user = max(0, after['user_usec'] - before['user_usec'])
        du_sys = max(0, after['system_usec'] - before['system_usec'])
        cpu_s = du / 1e6
        user_s = du_user / 1e6
        sys_s = du_sys / 1e6
        avg_cores = cpu_s / duration_s if duration_s > 0 else 0.0
        user_cores = user_s / duration_s if duration_s > 0 else 0.0
        sys_cores = sys_s / duration_s if duration_s > 0 else 0.0

        util_alloc = 100.0 * avg_cores / allocated if allocated > 0 else 0.0
        user_util_alloc = 100.0 * user_cores / allocated if allocated > 0 else 0.0
        sys_util_alloc = 100.0 * sys_cores / allocated if allocated > 0 else 0.0

        rows.extend([
            ('CGROUP_CPU_TIME_S', cpu_s),
            ('CGROUP_USER_CPU_TIME_S', user_s),
            ('CGROUP_SYSTEM_CPU_TIME_S', sys_s),
            ('AVG_CORES_USED', avg_cores),
            ('CPU_UTIL_ALLOCATED(%)', util_alloc),
            ('USR_UTIL_ALLOCATED(%)', user_util_alloc),
            ('SYS_UTIL_ALLOCATED(%)', sys_util_alloc),
        ])

        # Backward-compatible aliases. These are now correctly normalized to
        # the configured Spark executor-core capacity, not all host CPUs.
        rows.extend([
            ('USR_UTIL(%)', user_util_alloc),
            ('SYS_UTIL(%)', sys_util_alloc),
            ('CPU_UTIL(%)', util_alloc),
        ])
    else:
        # Fallback for older result directories without cgroup cpu.stat snapshots.
        if host.get('HOST_USR_UTIL(%)') is not None:
            rows.append(('USR_UTIL(%)', host['HOST_USR_UTIL(%)']))
        if host.get('HOST_SYS_UTIL(%)') is not None:
            rows.append(('SYS_UTIL(%)', host['HOST_SYS_UTIL(%)']))
        if host.get('HOST_CPU_UTIL(%)') is not None:
            rows.append(('CPU_UTIL(%)', host['HOST_CPU_UTIL(%)']))

    for k, v in host.items():
        if v is not None:
            rows.append((k, v))

    # Preserve the two legacy names, but make their host scope explicit above.
    if host.get('HOST_IOW_UTIL(%)') is not None:
        rows.append(('IOW_UTIL(%)', host['HOST_IOW_UTIL(%)']))
    if host.get('HOST_IDLE_UTIL(%)') is not None:
        rows.append(('IDL_UTIL(%)', host['HOST_IDLE_UTIL(%)']))

    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--result-dir', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()

    rows = metric_rows(args.result_dir)
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['METRIC', 'VALUE'])
        for k, v in rows:
            if isinstance(v, float):
                w.writerow([k, f'{v:.9f}'])
            else:
                w.writerow([k, v])


if __name__ == '__main__':
    main()
