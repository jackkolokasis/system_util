#!/usr/bin/env bash

###################################################
#
# file: myjstat.sh
#
# @Author:  Iacovos G. Kolokasis
# @Version: 19-01-2021
# @email:   kolokasis@ics.forth.gr
#
# @brief    This script tracks the memory usage 
###################################################

# Output file name
OUTPUT=$1        

while true; do
  head -n 2 /sys/fs/cgroup/memlim/memory.stat >> "${OUTPUT}"
  sleep 1
done
