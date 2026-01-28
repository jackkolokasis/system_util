#!/usr/bin/env python3

import os
import config
import matplotlib.pyplot as plt
import optparse
import matplotlib
matplotlib.use('Agg')

# Parse input arguments
usage = "usage: %prog [options]"
parser = optparse.OptionParser(usage=usage)
parser.add_option("-i", "--input", dest="input",
                  metavar="FILE", help="Input file")
parser.add_option("-o", "--output", dest="output", default="mem_usage.png",
                  help="Output image file (default: mem_usage.png)")
(options, args) = parser.parse_args()

if not options.input:
    parser.error("Missing --input")

anon_mem = []
page_cache_mem = []

# bytes -> GiB
BYTES_TO_GIB = 1024 ** 3

with open(options.input, "r") as f:
    for raw in f:
        line = raw.strip()
        if not line:
            continue

        cols = line.split()
        if len(cols) < 2:
            continue  # ignore malformed lines

        kind, value_str = cols[0], cols[1]

        # Skip anything unexpected (headers etc.)
        if kind not in ("anon", "file"):
            continue

        try:
            value = int(value_str)
        except ValueError:
            continue

        if kind == "anon":
            anon_mem.append(value)
        else:  # "file" == page cache
            page_cache_mem.append(value)

# Optional sanity check: your file usually has pairs anon/file per sample.
# If it’s mismatched, we plot up to the shortest length.
n = min(len(anon_mem), len(page_cache_mem))
anon_mem = anon_mem[:n]
page_cache_mem = page_cache_mem[:n]

# Convert to GiB for plotting
anon_gib = [v / BYTES_TO_GIB for v in anon_mem]
page_cache_gib = [v / BYTES_TO_GIB for v in page_cache_mem]

# Plot figure with fixed size
fig, ax = plt.subplots(figsize=config.fullfigsize)

# Grid
plt.grid(True, linestyle='--', color='grey', zorder=0)

# Prepare x-axis data (sample index)
time = range(1, n + 1)

plt.plot(time, anon_gib, color=config.B_color_cycle[0],
         label='Anonymous memory', zorder=2)
plt.plot(time, page_cache_gib, color=config.B_color_cycle[1],
         label='Page cache (file) memory', zorder=2)

# Axis name
plt.ylabel('Memory (GiB)', ha="center")
plt.xlabel('Time (samples)')

# Legend
plt.legend(loc='upper right', bbox_to_anchor=(0.65, 1.25), ncol=2)

# Ensure output directory exists (if user passes a path like out/plot.png)
out_dir = os.path.dirname(os.path.abspath(options.output))
if out_dir and not os.path.exists(out_dir):
    os.makedirs(out_dir, exist_ok=True)

# Save figure
plt.savefig(options.output, bbox_inches='tight')
