#!/bin/sh
# Gate-level (structural) Verilog flow, Icarus Verilog. Run from the project root:
#   bash scripts/run_gate.sh              normal run (behavioural dff, W = 4)
#   bash scripts/run_gate.sh nand         flip-flops built from NAND gates (dff_gates.v)
#   bash scripts/run_gate.sh w8           8-bit inputs, 20-bit accumulators
# Exits with a non-zero status if the compile fails or any line says FAIL.

FLAGS=""
case "$1" in
    nand) FLAGS="-DUSE_NAND_DFF" ;;
    w8)   FLAGS="-DW8" ;;
esac

LOG=$(mktemp)
iverilog -g2001 $FLAGS -o sim_gate.vvp rtl_gate/*.v tb_gate/tb_top.v || exit 1
vvp sim_gate.vvp | tee "$LOG"

if grep -q FAIL "$LOG"; then
    rm -f "$LOG"
    exit 1
fi
if ! grep -q "TOTAL" "$LOG"; then
    echo "no TOTAL line: the simulation did not finish"
    rm -f "$LOG"
    exit 1
fi
rm -f "$LOG"
exit 0
