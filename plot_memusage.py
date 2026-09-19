#!/usr/bin/env python3

import argparse
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True)
    ap.add_argument('-o', '--output', default='mem_usage.png')
    args = ap.parse_args()

    anon_mem = []
    page_cache_mem = []
    with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            cols = raw.split()
            if len(cols) < 2 or cols[0] not in ('anon', 'file'):
                continue
            try:
                value = int(cols[1])
            except ValueError:
                continue
            if cols[0] == 'anon':
                anon_mem.append(value)
            else:
                page_cache_mem.append(value)

    n = min(len(anon_mem), len(page_cache_mem))
    if n == 0:
        return

    gib = 1024.0 ** 3
    anon = [v / gib for v in anon_mem[:n]]
    file_mem = [v / gib for v in page_cache_mem[:n]]
    x = range(1, n + 1)

    fig, ax = plt.subplots(figsize=config.fullfigsize)
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.plot(x, anon, color=config.B_color_cycle[0], label='Anonymous memory')
    ax.plot(x, file_mem, color=config.B_color_cycle[1], label='Page cache (file)')
    ax.set_ylabel('Memory (GiB)')
    ax.set_xlabel('Sample (1 s interval)')
    ax.legend(loc='best')

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(args.output, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
