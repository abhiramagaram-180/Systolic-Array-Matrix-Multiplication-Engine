#!/bin/sh
# Simulator flow (laptop: Icarus Verilog). For the course simulator,
# only the compile/run commands in this file change; nothing else does.
# Run from the project root: bash scripts/run.sh

iverilog -g2001 -o sim.out rtl/*.v tb/tb_top.v || exit 1
vvp sim.out | tee sim.log

# Fail the script if any test printed FAIL
if grep -q FAIL sim.log; then
    exit 1
fi
rm -f sim.log
exit 0
