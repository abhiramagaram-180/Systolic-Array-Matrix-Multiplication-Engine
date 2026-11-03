# 4x4 Systolic Array Matrix Multiplier

This project is a Verilog-2001 design of a 4x4 systolic array that multiplies two 4x4 matrices of 8-bit unsigned numbers (C = A x B). It is output-stationary: each of the 16 processing elements (PEs) keeps one element of C in its own 20-bit accumulator, while A values flow to the right and B values flow down. A self-checking testbench compares the hardware result against a software reference for several hardcoded and random cases.

## Folder layout

```
rtl/        design files (pe.v, systolic_array.v, control.v, top.v)
tb/         testbench (tb_top.v)
scripts/    simulator commands (run.sh)
docs/       spec, explanations, hand trace, viva notes, report draft
README.md   this file
```

## How to run (laptop flow)

```bash
bash scripts/run.sh      # compile + simulate, prints PASS/FAIL per test
gtkwave dump.vcd         # view the waveform
```

`run.sh` exits with a non-zero status if any test prints FAIL.

## Files

| File | Job |
|------|-----|
| `rtl/pe.v` | One processing element: multiplies two 8-bit inputs, adds to a 20-bit accumulator, and passes the inputs on to the right and downward. |
| `rtl/systolic_array.v` | Builds the 4x4 grid of PEs and wires them together. |
| `rtl/control.v` | FSM (IDLE/RUN/DONE) and cycle counter that feeds the correct A and B values to the array each cycle and raises `done`. |
| `rtl/top.v` | Connects the controller to the array; this is the design's top module. |
| `tb/tb_top.v` | Testbench with hardcoded and random matrices, checked against a software reference. |
| `scripts/run.sh` | Compiles and runs the simulation and reports failure through its exit code. |
| `docs/spec.md` | The design specification. |
| `docs/control_explained.md` | Beginner explanation of `control.v`. |
| `docs/pe_and_array_explained.md` | Beginner explanation of `pe.v`, `systolic_array.v` and `top.v`. |
| `docs/handtrace_2x2.md` | Worked 2x2 example, cycle by cycle. |
| `docs/viva_notes.md` | 25 likely viva questions with short answers. |
| `docs/report_draft.md` | Draft of the project report. |

## Parameters

| Parameter | Value |
|-----------|-------|
| Array size N | 4 x 4 |
| Inputs | 8-bit unsigned |
| Accumulators | 20-bit |
| Latency | 10 cycles = 3N - 2 (t = 0..9); `done` goes high the cycle after t = 9 |

## Simulator

**TODO-update-when-professor-confirms**

Currently the project is simulated with Icarus Verilog 0.9.7 using the commands in `scripts/run.sh`:

```
iverilog -g2001 -o sim.out rtl/*.v tb/tb_top.v
vvp sim.out
```

The course simulator is not decided yet. When it is, only the commands in `scripts/run.sh` (and this section) need to change. The design and testbench use plain Verilog-2001 only.

## Team

Author: Abhiram Agaram (PES1UG25CS017)

Team members:
- [Member 2 name]
- [Member 3 name]
- [Member 4 name]
