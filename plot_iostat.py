#!/usr/bin/env python3

import argparse
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import config
from parse_iostat import parse_iostat, read_mb_s, write_mb_s, _metric


def norm_dev(d):
    return os.path.basename(d.rstrip('/'))


def plot_metric(records, devices, extractor, ylabel, title, output):
    fig, ax = plt.subplots(figsize=config.fullfigsize)
    have_data = False

    for idx, dev in enumerate(devices):
        rows = records.get(dev, [])
        vals = [extractor(r) for r in rows]
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        have_data = True
        x = range(1, len(vals) + 1)
        color = config.B_color_cycle[idx % len(config.B_color_cycle)]
        ax.plot(x, vals, label=dev, color=color)

    if not have_data:
        plt.close(fig)
        return

    ax.grid(True, linestyle='--', alpha=0.4)
    ax.set_title(title, fontsize=config.fontsize)
    ax.set_xlabel('Sample (1 s interval)', fontsize=config.fontsize)
    ax.set_ylabel(ylabel, fontsize=config.fontsize)
    ax.legend(loc='best')
    fig.savefig(output, bbox_inches='tight')
    plt.close(fig)


def parse_cpu(path):
    """Parse avg-cpu blocks from iostat dynamically by header names."""
    samples = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = iter(f)
        for raw in lines:
            line = raw.strip().replace(',', '.')
            if not line.startswith('avg-cpu:'):
                continue
            header = line.split()[1:]
            try:
                values_line = next(lines).strip().replace(',', '.')
            except StopIteration:
                break
            vals = values_line.split()
            if len(vals) < len(header):
                continue
            try:
                samples.append({k: float(v) for k, v in zip(header, vals)})
            except ValueError:
                continue
    return samples


def plot_cpu(path, outdir):
    samples = parse_cpu(path)
    if not samples:
        return
    keys = [('%user', '%usr'), ('%system', '%sys'), ('%iowait',), ('%idle',)]
    labels = ['User', 'System', 'IOwait', 'Idle']
    fig, ax = plt.subplots(figsize=config.fullfigsize)
    x = range(1, len(samples) + 1)
    for idx, (names, label) in enumerate(zip(keys, labels)):
        vals = []
        for row in samples:
            value = None
            for name in names:
                if name in row:
                    value = row[name]
                    break
            vals.append(0.0 if value is None else value)
        ax.plot(x, vals, label=label,
                color=config.B_color_cycle[idx % len(config.B_color_cycle)])
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.set_ylim(0, 100)
    ax.set_title('Host CPU utilization (iostat)', fontsize=config.fontsize)
    ax.set_xlabel('Sample (1 s interval)', fontsize=config.fontsize)
    ax.set_ylabel('CPU utilization (%)', fontsize=config.fontsize)
    ax.legend(loc='best')
    fig.savefig(os.path.join(outdir, 'cpu.png'), bbox_inches='tight')
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True)
    ap.add_argument('-o', '--outputPath', required=True)
    ap.add_argument('-s', '--storage', action='append', required=True,
                    help='Device name; may be repeated')
    args = ap.parse_args()

    os.makedirs(args.outputPath, exist_ok=True)
    devices = [norm_dev(d) for d in args.storage]
    records = parse_iostat(args.input, devices)

    plot_metric(records, devices, read_mb_s,
                'Read throughput (MB/s)', 'Read throughput',
                os.path.join(args.outputPath, 'r_thrput.png'))
    plot_metric(records, devices, write_mb_s,
                'Write throughput (MB/s)', 'Write throughput',
                os.path.join(args.outputPath, 'wr_thrput.png'))
    plot_metric(records, devices, lambda r: _metric(r, 'aqu-sz', 'avgqu-sz'),
                'Average queue size', 'Device queue size',
                os.path.join(args.outputPath, 'avg_qu_sz.png'))
    plot_metric(records, devices, lambda r: _metric(r, '%util'),
                'Device utilization (%)', 'Device utilization',
                os.path.join(args.outputPath, 'util.png'))
    plot_metric(records, devices, lambda r: _metric(r, 'r_await', 'await'),
                'Read await (ms)', 'Read latency',
                os.path.join(args.outputPath, 'read_await.png'))
    plot_metric(records, devices, lambda r: _metric(r, 'w_await', 'await'),
                'Write await (ms)', 'Write latency',
                os.path.join(args.outputPath, 'write_await.png'))

    plot_cpu(args.input, args.outputPath)


if __name__ == '__main__':
    main()
