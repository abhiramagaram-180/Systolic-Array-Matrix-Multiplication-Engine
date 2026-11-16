# Gate-level (structural) design

This document explains the **gate-level version** of the 4x4 systolic array multiplier, block by block, starting with the full adder. The same design exists twice:

- as **structural Verilog** in `rtl_gate/` (only gate primitives, module instances and one D flip-flop module), and
- as a **Logisim circuit** in `logisim/systolic_gate_level.circ` (only AND / OR / XOR / NOT gates, splitters, tunnels, constants and D flip-flops).

Both have exactly the same hierarchy and the same number of gates (see the gate-count table). The original behavioural versions (`rtl/` and `logisim/systolic_4x4_auto.circ`, which use `+`, `*`, `==`, Adder, Multiplier, Register, Counter, ROM) are unchanged.

## Parameters of the gate-level version

| Parameter | Value |
|-----------|-------|
| Array | 4 x 4, output-stationary, A flows right, B flows down |
| Input width W | **4 bits**, unsigned (0..15) |
| Accumulator width | **10 bits** (the largest result is 4 x 15 x 15 = 900, and 2^10 = 1024) |
| Latency | 10 cycles (3N - 2 for N = 4): PE(i,j) sees A[i][k] and B[k][j] at t = i + j + k |
| Switch to 8 bits | W = 8 and accumulator 20 bits (see "Switching to 8 bits" below) |

The design rule is simple: **everything is built from 2-input AND, OR, XOR gates and NOT gates**, plus flip-flops. The only place where behaviour is described is the small module `dff` (a D flip-flop). In Logisim the only place a flip-flop part is used is the circuit called `DFF`.

## 1. Full adder (`fa`)

A full adder adds three 1-bit numbers: `a`, `b` and the carry coming in, `cin`. It gives a 1-bit `sum` and a 1-bit carry out, `cout`.

| a | b | cin | sum | cout |
|---|---|-----|-----|------|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 0 | 1 | 1 | 0 |
| 0 | 1 | 0 | 1 | 0 |
| 0 | 1 | 1 | 0 | 1 |
| 1 | 0 | 0 | 1 | 0 |
| 1 | 0 | 1 | 0 | 1 |
| 1 | 1 | 0 | 0 | 1 |
| 1 | 1 | 1 | 1 | 1 |

`sum` is 1 when an odd number of inputs are 1, which is exactly XOR of all three. `cout` is 1 when at least two inputs are 1.

```
t    = a XOR b
sum  = t XOR cin
cout = (a AND b) OR (t AND cin)
```

```
 a ──┬──[XOR]── t ──┬──[XOR]── sum
 b ──┤  (1)         │   (2)
     │              │     ^
     │              │    cin
     └──[AND]── g   └──[AND]── p      cout = g OR p   -> [OR]
        (3)            (4)                    (5)
```

Five gates: 2 XOR, 2 AND, 1 OR. Everything else in the design that adds numbers is made of copies of this block.

## 2. Ripple-carry adder (`adder_n`)

To add two N-bit numbers, put N full adders in a row. The carry-out of bit i is the carry-in of bit i + 1 (the carry "ripples" along). The first carry-in is `cin`; the last carry-out is `cout`.

```
 a3 b3     a2 b2     a1 b1     a0 b0
  |  |      |  |      |  |      |  |
 [FA3]<-c3-[FA2]<-c2-[FA1]<-c1-[FA0]<-- cin
  |  |      |  |      |  |      |
 cout s3     s2         s1       s0
```

Gates: 5 x N (20 for 4 bits, 50 for 10 bits). It is slow for wide numbers because the carry must travel through every bit, but it is the simplest adder to explain.

## 3. Array multiplier (`mult_4x4`)

Multiplying 4-bit numbers works like multiplication on paper in binary. For each bit `b[j]` of the second number, make a *partial product*: `a AND b[j]` (a row of AND gates). Row j is shifted j places to the left. Then add all the rows.

```
              a3 a2 a1 a0
          x   b3 b2 b1 b0
          ----------------
              a3b0 a2b0 a1b0 a0b0      row 0 (4 AND gates)
         a3b1 a2b1 a1b1 a0b1           row 1
    a3b2 a2b2 a1b2 a0b2                row 2
a3b3 a2b3 a1b3 a0b3                    row 3
------------------------------------
p7 p6 p5 p4 p3 p2 p1 p0
```

In the hardware, row 0 is the first partial sum. Each next row is added with one 4-bit ripple adder: the previous sum is shifted right by one place (its lowest bit is already a final product bit) and the carry of the previous addition becomes the new top bit. So there are 3 adders for 4 rows. Product bit j is the lowest bit of row j's sum; the last carry and the upper bits of the last sum are product bits 4..7.

Gates: 16 AND + 3 adders x 20 = **76**. The result is 8 bits (largest 15 x 15 = 225).

## 4. D flip-flop (`dff`) and the register (`reg_n`)

A **D flip-flop** remembers one bit. On every rising edge of the clock it copies its input `d` to its output `q` and keeps that value until the next edge. All memory in the design (the accumulators, the delay registers, the counter and the run flag) is made of D flip-flops.

In Verilog the flip-flop is the only module with an `always` block (`rtl_gate/dff.v`). It can be swapped for a version made only of NAND and NOT gates (`rtl_gate/dff_gates.v`, a master-slave pair of latches, 10 gates per flip-flop). In Logisim it is the library part "D Flip-Flop", used only inside the circuit `DFF`.

A **register** (`reg_n`) is N flip-flops side by side with a *synchronous clear*. In front of each flip-flop sits an AND gate:

```
d_gated = d AND (NOT clear)
```

When `clear = 1` the AND gate forces 0 into the flip-flop, so the register becomes 0 at the next clock edge. When `clear = 0` the data passes through. It is "synchronous" because nothing happens until the clock edge.

Gates: 1 NOT + N AND (5 for 4 bits, 11 for 10 bits), plus N flip-flops.

## 5. Processing element (`pe`)

One cell of the array. Every clock edge:

- `acc <= acc + a_in * b_in` (multiplier + adder + 10-bit register),
- `a_out <= a_in` and `b_out <= b_in` (two 4-bit registers) so the neighbours get the values one clock later.

```
a_in --+--------------------------------------> [REG 4] --> a_out
       |
       +--> [ MULT 4x4 ] --8 bits--> (pad with 0,0 to 10 bits) --> [ADDER 10] --> [REG 10] --> acc
b_in --+                                                                ^                |
       |                                                                +----------------+
       +--------------------------------------> [REG 4] --> b_out
                                            clear goes to all three registers
```

The product has 8 bits; the accumulator has 10, so two constant 0 bits are added on top (in Logisim these are ground wires joined with a splitter, not an extender part). Gates: 76 + 50 + 11 + 5 + 5 = **147**, flip-flops: 10 + 4 + 4 = 18.

## 6. Counter (`counter4`)

A 4-bit counter built from a register and an incrementer. Bit i flips when all the bits below it are 1 and counting is enabled (`en`):

```
toggle0 = en
toggle1 = en AND q0
toggle2 = toggle1 AND q1
toggle3 = toggle2 AND q2
next[i] = q[i] XOR toggle[i]
```

`clear = 1` loads 0 (through the register's AND gates); `en = 0` holds the value. Gates: 3 AND + 4 XOR + the register's 5 = **12**, flip-flops: 4.

## 7. Decoder and selector (`tdec4`, `select4`)

The behavioural design used a ROM (or Verilog arithmetic) to give row i the element A[i][t] and column j the element B[t][j]. At gate level this is a **multiplexer built from gates**.

`tdec4` turns the counter value `t` into four select lines (one-hot): `sel[k] = 1` when t = k for k = 0..3, and all lines are 0 when t >= 4. Inside: `lt4 = NOT t3 AND NOT t2` ("t is below 4") and a 2-to-4 decoder of t1, t0, then `sel[k] = lt4 AND decoded[k]`. Gates: 4 NOT + 1 + 4 + 4 AND = **13**.

`select4` has four W-bit inputs and one W-bit output. For each bit: `y = (sel0 AND d0) OR (sel1 AND d1) OR (sel2 AND d2) OR (sel3 AND d3)`, made of 4 AND and 3 OR gates (two ORs of pairs, one OR of the pairs). Gates: 7 per bit, **28** for 4 bits. When no select line is 1 (t >= 4) the output is 0, which is the "zero after the data" the array needs.

## 8. Skew registers (`skew_chain`, SKEW_1..3)

All 4 rows and 4 columns start at t = 0 from the selectors, but PE(i,j) must see A[i][k] and B[k][j] at t = i + j + k. Each hop between PEs already costs one clock (the `a_out` / `b_out` registers), so **row i must start i cycles later and column j must start j cycles later**.

This is done with delay lines: row i passes through i registers (so its value is delayed by i clock edges), column j through j registers. Row 0 and column 0 have none. A delay of i cycles turns "A[i][t]" into "A[i][t-i]". The registers are cleared by `clear`, so before the data arrives they give 0, which does nothing in a multiply-accumulate.

Registers needed: rows 1 + 2 + 3 = 6 and columns 6 = 12 registers of 4 bits = **48 flip-flops** and 60 gates (the AND gates of the clear).

## 9. Controller (`control`)

Signals (all made of gates and flip-flops):

| Signal | Meaning | Gates |
|--------|---------|-------|
| `run` | flip-flop: a run was started and is not cleaned up yet | 1 flip-flop |
| `clear` | `start AND (NOT run)`: wipes the datapath before a run | NOT + AND |
| `done` | `t == 10` (binary 1010: `t3 AND NOT t2 AND t1 AND NOT t0`) | 2 NOT + 3 AND |
| `busy` | `run AND (NOT done)`: counter enable | NOT + AND |
| next `run` | `(start OR busy) AND (NOT rst)` | OR + NOT + AND |
| counter clear | `clear OR rst` | OR |

Timeline: `start` high for one clock -> `clear` is 1 during that cycle, and at the clock edge everything is cleared, `run` becomes 1 and t stays 0. While `busy`, t counts 1, 2 ... 10. At t = 10 `done` is 1 and `busy` is 0, so the counter stops. At the next edge `run` falls back to 0. A `start` that arrives in the `done` cycle (when `run` is still 1) does not clear anything: a new start is accepted one clock after `done`. Gates: 13 + counter's 12 = **25**, flip-flops: 5.

## 10. Feeder, systolic array and top

- **feeder**: `tdec4` + 8 `select4` (4 rows, 4 columns) + the skew lines. 13 + 224 + 60 = **297** gates and 48 flip-flops.
- **systolic_array**: 16 PEs joined by `a_link` / `b_link` wires: A goes right, B goes down, `clk` and `clear` go to every PE. 16 x 147 = **2352** gates and 288 flip-flops.
- **top**: control + feeder + array.

```
 start,rst,clk --> [ CONTROL ] --t--> [ FEEDER ] --a_row_in, b_col_in--> [ SYSTOLIC 4x4 ] --> C
                        |  clear ----------^---------------------------------^
                        +--> done
```

## Gate count (W = 4, accumulator 10 bits)

Counts are 2-input gates (NOT counted as one). They come from the Logisim generator and were cross-checked against the compiled Verilog (`iverilog -s top`, counting the primitives): **2674 gates and 341 flip-flops** in both.

| Block | Gates | Flip-flops |
|-------|------:|-----------:|
| FA | 5 | 0 |
| ADDER_4 / ADDER_10 | 20 / 50 | 0 |
| MULT_4x4 | 76 | 0 |
| REG_4 / REG_10 | 5 / 11 | 4 / 10 |
| PE | 147 | 18 |
| COUNTER4 | 12 | 4 |
| TDEC4 | 13 | 0 |
| SELECT4 | 28 | 0 |
| SKEW_1 / SKEW_2 / SKEW_3 | 5 / 10 / 15 | 4 / 8 / 12 |
| CONTROL | 25 | 5 |
| FEEDER | 297 | 48 |
| SYSTOLIC_4x4 (16 PEs) | 2352 | 288 |
| **TOP** | **2674** | **341** |

By type for the whole design: AND 1446, OR 450, XOR 708, NOT 70 = 2674. If the 341 flip-flops are also built from gates (`-DUSE_NAND_DFF`, 8 NAND + 2 NOT each), the total becomes 2674 + 3410 = 6084 gates.

## Behavioural versus gate-level

| | Behavioural | Gate-level (structural) |
|---|---|---|
| Verilog | `rtl/` (pe.v, systolic_array.v, control.v, top.v) with `+`, `*`, `==`, `always`, ROM-like selection by arithmetic | `rtl_gate/` (fa, adder_n, mult_4x4, dff, reg_n, pe, counter4, tdec4, select4, skew_chain, feeder, control, systolic_array, top) with only gate primitives and instances |
| Verilog testbench | `tb/tb_top.v`, run with `scripts/run.sh` | `tb_gate/tb_top.v`, run with `scripts/run_gate.sh` (also unit tests for fa, adder_n, mult_4x4) |
| Logisim | `logisim/systolic_4x4_auto.circ` (Adder, Multiplier, Register, Counter, Comparator, ROM) | `logisim/systolic_gate_level.circ` (gates, splitters, tunnels, constants, D flip-flops) |
| Width | 8-bit inputs, 20-bit accumulators | 4-bit inputs, 10-bit accumulators (8 / 20 with one setting) |
| Clear | Verilog: synchronous; Logisim: asynchronous Register clear | synchronous in both |
| Test data | A_flat / B_flat (Verilog), ROM images (Logisim) | A_flat / B_flat (Verilog); in Logisim, 8 hard-wired constants (A_row0..3, B_col0..3) |
| Gate count | not defined (library blocks) | 2674 gates + 341 flip-flops |

### Mapping between the gate-level Verilog and the gate-level Logisim circuits

| Verilog module (`rtl_gate/`) | Logisim circuit |
|---|---|
| fa | FA |
| adder_n | ADDER_4, ADDER_10 |
| mult_4x4 | MULT_4x4 |
| dff | DFF (the only circuit that contains a flip-flop part) |
| reg_n | REG_4, REG_10 |
| pe | PE |
| counter4 | COUNTER4 |
| tdec4 | TDEC4 |
| select4 | SELECT4 |
| skew_chain | SKEW_1, SKEW_2, SKEW_3 |
| control | CONTROL |
| feeder | FEEDER |
| systolic_array | SYSTOLIC_4x4 |
| top | TOP |
| testbench cases | main (hand_picked with a Clock) and `case_zeros`, `case_ones`, `case_identity`, `case_all_max`, `case_hand_picked`, `case_single_hot`, `case_random` (matrices hard-wired as constants) |

Two small differences come from Logisim: a bus can be at most 64 bits wide, so the Verilog buses `A_flat` / `B_flat` (64 bits each) and `C_flat` (160 bits) become 8 buses of 16 bits (`A_row0..3`, `B_col0..3`, element k in bits [4k +: 4], the same layout as `A_flat`) and 16 separate 10-bit outputs `C00..C33`.

## How to run

```bash
bash scripts/run_gate.sh              # structural Verilog: unit tests + system tests
bash scripts/run_gate.sh nand         # same, with flip-flops built from NAND gates
bash scripts/run_gate.sh w8           # 8-bit inputs, 20-bit accumulators
python scripts/check_gate_only.py     # proves that rtl_gate/ uses only gates (except dff.v)
python logisim/make_cases_gate.py     # prints the test matrices and the expected C
python logisim/gate_generator/gen_gate_level.py            # regenerate logisim/systolic_gate_level.circ
python logisim/gate_generator/check_circuit.py             # net checker for every circuit
python logisim/gate_generator/verify_gate_level.py         # headless Logisim simulation, bottom-up
```

Open `logisim/systolic_gate_level.circ` in Logisim-evolution. The circuit `main` has a Clock, two input pins (`rst`, `start`) and an LED / hex display. Click `rst` to 1, tick the clock twice (F9 twice), set `rst` back to 0, set `start` to 1, tick once, set `start` to 0, then keep ticking: after 10 more ticks `done` lights up and `C00..C33` show the result (hand-picked case). To see a block, double-click it in the circuit list (FA first).

### Switching to 8 bits

The generator takes the width as a setting:

```bash
python logisim/gate_generator/gen_gate_level.py --w 8 --acc 20 --out logisim/systolic_gate_level_w8.circ
```

The Verilog needs no edit: the modules have parameters `W` and `ACC` (defaults 4 and 10); the testbench switches both with `-DW8` (`bash scripts/run_gate.sh w8`).

## Viva questions (structural versus behavioural design)

**1. What is the difference between a structural and a behavioural description?**
A behavioural description says *what* the circuit does (`acc <= acc + a * b;`) and lets the tool choose the hardware. A structural description says *how it is built*: which gates and which modules are connected to which wires. Here every adder, multiplier and counter is spelled out with gates.

**2. Why is `dff` the only module with behaviour?**
A gate-level netlist needs a memory element, and the memory element is the one thing that is described by what it does (copy `d` to `q` on a clock edge). Keeping it in one module means it can be replaced by a flip-flop made of NAND gates (`dff_gates.v`) without changing anything else.

**3. Explain the full adder.**
`sum = a XOR b XOR cin` (1 if an odd number of inputs are 1) and `cout = (a AND b) OR ((a XOR b) AND cin)` (1 if at least two inputs are 1). It needs 5 gates.

**4. How does the array multiplier work and how many gates does it use?**
It forms the partial products with AND gates (`a AND b[j]`, 16 gates) and adds the shifted rows with 3 ripple adders of 4 full adders each (60 gates): 76 gates. The result is 8 bits.

**5. What is a ripple-carry adder and what is its disadvantage?**
N full adders in a row, each carry-out feeding the next carry-in. It is small and simple, but the carry has to travel through all bits, so a wide adder is slow. A carry-lookahead adder would be faster but bigger and harder to explain.

**6. How does the synchronous clear work in `reg_n`?**
An AND gate in front of every flip-flop computes `d AND (NOT clear)`. When `clear` is 1 the flip-flop loads 0 at the next clock edge; otherwise it loads `d`.

**7. How does the counter count with only XOR and AND gates?**
Bit i must flip when all lower bits are 1 (and counting is enabled), so `toggle[i]` is an AND chain of the lower bits and `en`, and the next value of bit i is `q[i] XOR toggle[i]`. The four flip-flops store the result.

**8. How do the selectors replace the ROM?**
`tdec4` decodes the counter into four one-hot select lines for t = 0..3. `select4` ANDs each data value with its select line and ORs the results, so at time t it outputs element t, and 0 when no line is active (t >= 4).

**9. Why are there skew registers, and why i for row i?**
Each hop between neighbouring PEs costs one clock, so PE(i,j) gets A[i][k] j clocks after row i's input and B[k][j] i clocks after column j's input. To make them meet at t = i + j + k, row i is delayed by i clocks and column j by j clocks before entering the array (i or j registers in series).

**10. What must change to use 8-bit inputs?**
Set W = 8 and the accumulator to 20 bits (the largest sum is 4 x 255 x 255 = 260100 < 2^20). No Verilog source changes (parameters), and the Logisim generator is run with `--w 8 --acc 20`. The number of gates grows (the multiplier has 64 AND gates and 7 x 8 full adders instead of 16 and 12).

## Verification summary

Everything below was run on Icarus Verilog 0.9.7 and on Logisim-evolution v5.0.0 (its headless test-vector mode).

### Structural Verilog (`bash scripts/run_gate.sh`)

| Run | Result |
|-----|--------|
| normal (W = 4) | 11 of 11 test groups pass: fa (all 8 inputs), adder_n (all inputs), mult_4x4 (all 256 pairs), zeros, ones, identity with a non-symmetric B, all 15 (every C = 900), hand-picked, single non-zero cell, 50 random matrices, 2 back-to-back runs without reset. Each run also checks that `done` comes exactly 10 cycles after `start`. |
| `nand` (flip-flops built from NAND gates) | 11 of 11 pass |
| `w8` (8-bit inputs, 20-bit accumulators) | 11 of 11 pass (takes 1.5 to 3 minutes: the multiplier unit test runs all 65536 pairs) |
| `python scripts/check_gate_only.py` | pass: no behavioural keyword or operator outside `dff.v`; `assign` only for pure wiring; only and / or / xor / not primitives |
| `bash scripts/run.sh` (original behavioural design) | 8 of 8 pass (unchanged) |

Controls: seven deliberate faults (a wrong carry gate, the same skew for every row, `done` decoded at the wrong time, a register without clear, a wrong decoder output, a selector that drops an input, a broken NAND flip-flop) were each caught by the testbench (at most 5 of 11 groups still passed), and `run_gate.sh` exits with status 1 when a design is broken. The lint script rejects planted behavioural code.

### Logisim gate-level circuit (`python logisim/gate_generator/verify_gate_level.py`)

36 test runs, 0 failed. Each bottom-up step uses a Logisim test vector; the expected values come from plain Python, not from the circuits.

| Circuit | What was checked | Rows passed |
|---------|------------------|-------------|
| FA | all 8 input combinations | 8 / 8 |
| ADDER_4 / ADDER_10 | all 512 inputs / 306 inputs including carries | 512 / 306 |
| MULT_4x4 | all 256 pairs | 256 / 256 |
| DFF, REG_4, REG_10 | edge triggering, hold, synchronous clear | 7 / 18 / 18 |
| PE | 3 x 4 gives 12 after one tick and 24 after two; clear; largest value | 26 / 26 |
| COUNTER4 | count, wrap 15 to 0, hold, clear | 51 / 51 |
| TDEC4, SELECT4 | t = 0..15; random data with every select | 16 / 300 |
| SKEW_1, SKEW_2, SKEW_3 | delay of 1, 2, 3 clock edges | 39 each |
| CONTROL | reset, two runs, `done` at t = 10, start ignored while running or in the `done` cycle | 106 / 106 |
| FEEDER | skewed feed at t = 0..10 (two matrices) | 36 each |
| SYSTOLIC_4x4 | all 16 accumulators after every clock edge (hand-picked and all-maximum) | 39 each |
| TOP | every case, two back-to-back runs: t, `done` and all 16 C values after every clock edge; plus 20 random matrices in a row | 82 per case, 748 |
| case wrappers (7) | the hard-wired constants, two runs each | 80 each |
| `main` with the real Clock | tty mode: C equals the expected matrix, `done` rises only on the last step | pass |
| negative control | a wrong expected value for C23 | fails, as it must |
| 8-bit circuit (`--w 8 --acc 20`) | the same bottom-up suite, with 471 sampled multiplier pairs instead of all 65536; accumulators 20 bits; net checker also clean | 36 runs, 0 failed |

### Cross-checks

- **Verilog against Logisim:** the structural Verilog was run on the same seven cases and its C, `t` and `done` were compared after every clock edge with the same Python model the Logisim tests use: 70 of 70 checks (7 cases x 10 edges) match. The final matrices are therefore identical in both.
- **Gate counts:** the Logisim generator and the compiled Verilog (`iverilog -s top`, counting primitives) both give 2674 two-input gates and 341 flip-flops at W = 4, and 8322 gates and 677 flip-flops at W = 8.
- **Net checker** (`logisim/gate_generator/check_circuit.py`) runs on every one of the 26 circuits: no shorts, no undriven inputs, no unconnected ports, no dangling wires, no accidental connections, no wire crossings. It reads the XML itself, independently of the generator. Five planted faults (two outputs on one net, a pin with no wire, an unconnected gate input, a wire running through a port, a missing gate) were each reported.

### Two Logisim-evolution 5.0.0 quirks found while building it

1. The loader **hangs** when a subcircuit instance has the same label as a circuit (ignoring case), for example instance `control` of circuit `CONTROL`. The generator now names such instances `u_control`, and the checker reports the problem.
2. A splitter that puts **several bits on one end** (16 bits into 4 lanes of 4) reads as all unknown unless every bit assignment is written in the file. The generator writes them, and the checker requires them.

### Not verified

- I could not open the Logisim window, so how the circuits look on the canvas was only checked with a rough preview that I drew from the file (parts, wires and tunnel names), not in Logisim itself. Tunnel labels and body sizes could overlap slightly on screen.
- The clicking procedure in `main` (rst, start, F9) was not run by hand. What was run is the same circuit in Logisim's tty mode with the real Clock, with start tied to 1 and rst to 0.
- The optional NAND flip-flop (`dff_gates.v`) works in the zero-delay Icarus simulation with all tests passing, but a latch built from cross-coupled gates can race in simulators with other delay models; it was not tried in any other simulator.
