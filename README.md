# system_util changes

## CPU accounting

`start_statistics.sh` snapshots cgroup-v2 `cpu.stat` before the measured phase and
`stop_statistics.sh` snapshots it again at the end. `extract-data.sh` computes
actual cgroup CPU seconds and normalizes average utilization to the configured
Spark executor-core capacity.

`run.sh` now calls:

```bash
./system_util/start_statistics.sh \
  -d "${RUN_DIR}" \
  -g memlim \
  -c "$(( ACTIVE_EXEC_CORES * ACTIVE_NUM_EXECUTORS ))"
```

The main CPU fields in `system.csv` are:

- `CGROUP_CPU_TIME_S`: actual CPU seconds charged to the Spark cgroup.
- `CGROUP_USER_CPU_TIME_S`: actual user CPU seconds.
- `CGROUP_SYSTEM_CPU_TIME_S`: actual kernel/system CPU seconds.
- `AVG_CORES_USED`: average fully-utilized CPU equivalents during measurement.
- `CPU_UTIL_ALLOCATED(%)`: `AVG_CORES_USED / configured_executor_cores * 100`.
- `HOST_*`: host-wide mpstat metrics, retained separately.

`CPU_UTIL_ALLOCATED(%)` can exceed 100% because Spark executor cores are task
slots, not an OS CPU quota or CPU affinity mask. GC, driver, worker, and other
threads in the cgroup can use additional CPUs. If a strict N-core experiment is
required, use cpuset/cpu.max in addition to this accounting.

## iostat

Collection uses:

```bash
LC_ALL=C iostat -x -m -y 1
```

`-y` suppresses the first report (which otherwise represents time since boot),
and `LC_ALL=C` stabilizes headers and decimal separators. Parsing is by header
name rather than fixed column offsets, so both older and newer sysstat layouts
are supported. The parser handles old `avgrq-sz/avgqu-sz` and newer
`rareq-sz/wareq-sz/aqu-sz` layouts, and either MB/s or kB/s throughput fields.

`/proc/diskstats` devices are matched exactly by device name and read/write
sector deltas are converted with 512 bytes per kernel sector.

## Process lifetime

The monitor PIDs are stored per result directory. `stop_statistics.sh` kills
only those PIDs instead of running global `killall -9 iostat mpstat`.

## Files

- `start_statistics.sh` / `stop_statistics.sh`: collection lifecycle.
- `extract-data.sh`: aggregate extraction.
- `parse_system_stats.py`: mpstat + cgroup CPU parser.
- `disk_util.sh` / `parse_iostat.py`: robust disk parser.
- `plot_iostat.py`: header-driven iostat plots.
- `mem_usage.sh`: no longer assumes anon/file are the first two memory.stat lines.
- `plot_memusage.py`: fixed matplotlib backend ordering and cleanup.
- `run.sh`: passes configured executor-core capacity to system statistics.
- `parse_results.sh`: consumes actual cgroup CPU seconds when available.
