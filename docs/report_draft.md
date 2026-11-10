# Design and Verification of a 4x4 Systolic Array Matrix Multiplier

Author: Abhiram Agaram (PES1UG25CS017)
Team members: Akshay Swami, Amogha, Hrushikesh, Abhiram Agaram

## Abstract

This report describes a Verilog-2001 implementation of a 4x4 output-stationary systolic array that multiplies two matrices of 8-bit unsigned integers into a matrix of 20-bit results. A small controller feeds the rows and columns with the right delays, so no skew buffers are needed. The multiplication completes in 10 clock cycles (3N - 2 for N = 4). The design is verified by a self-checking testbench with hardcoded matrices (identity, zeros, ones, maximum values, single non-zero cell) and 50 random matrix pairs, all compared with a software reference. All tests pass in Icarus Verilog 0.9.7. The Verilog design is the verified reference model; the same architecture is then redrawn by hand in Logisim (version [TODO-fill-in-version-used]) with ROMs, delay registers and a counter, and its results are compared with the reference values.

## 1. Introduction

Matrix multiplication is at the core of graphics, signal processing and machine learning. Doing it with one multiplier is slow; doing it with a large parallel structure needs a lot of wiring and memory bandwidth. A systolic array solves this by using many identical, simple processing elements (PEs) that exchange data only with their neighbours. The goal of this project is to design, simulate and verify a small, readable systolic matrix multiplier suitable for a course project.

## 2. Background

### 2.1 Matrix multiplication

For N x N matrices, C = A x B where C[i][j] = sum over k = 0..N-1 of A[i][k] x B[k][j]. For N = 4 this takes 64 multiplications and 48 additions.

### 2.2 Systolic arrays

A systolic array is a regular grid of PEs. Data moves through the grid one step per clock cycle and each PE does a small operation (here multiply-accumulate). There are different dataflows. In the **output-stationary** style used here, each PE keeps one output element and the input values stream past it. Because each input value is passed from PE to PE, it is read only once but used by a whole row or column (data reuse), and all wires are short and local.

## 3. Architecture

### 3.1 Block diagram

```
          A_flat, B_flat, start, rst, clk
                      |
                +-----v-----+
                |  control  |  FSM (IDLE/RUN/DONE) + cycle counter t
                +--+--+--+--+--> done
   a_row_in[31:0]  |  |  | clear
   b_col_in[31:0]  |  |  |
                +--v--v--v--------------------+
                |        systolic_array       |
                |   b_col_in[0..3] (from top) |
                |       |     |     |     |   |
                |  a -> PE -> PE -> PE -> PE  |
                |  a -> PE -> PE -> PE -> PE  |
                |  a -> PE -> PE -> PE -> PE  |
                |  a -> PE -> PE -> PE -> PE  |
                +-----------------+-----------+
                                  |
                           C_flat[319:0]
```

A flows to the right along each row, B flows down along each column. `top` contains `control` and `systolic_array`.

### 3.2 Module descriptions

- **pe**: multiplies the 8-bit inputs `a_in` and `b_in`, adds the 16-bit product to the 20-bit accumulator `acc` every clock, and registers `a_in` to `a_out` and `b_in` to `b_out` so neighbours see them one cycle later. `rst` or `clear` zeros the accumulator and the output registers.
- **systolic_array**: a 4x4 grid of `pe` instances created with `generate` loops. Two wires, `a_link` (4x5 bytes) and `b_link` (5x4 bytes), connect each PE to its neighbours. The 16 accumulators are packed in `c_flat`.
- **control**: a three-state FSM (IDLE -> RUN -> DONE) with a counter `t` that runs 0..9. In RUN it feeds row i with A[i][t-i] and column j with B[t-j][j] when the index is 0..3, otherwise 0. It generates a one-cycle `clear` when `start` is accepted and raises `done` in DONE.
- **top**: connects `control` and `systolic_array`.

### 3.3 Data format

Flat buses in row-major order: A[i][k] at `A_flat[(i*4+k)*8 +: 8]`, B[k][j] at `B_flat[(k*4+j)*8 +: 8]`, C[i][j] at `C_flat[(i*4+j)*20 +: 20]`.

## 4. Timing and dataflow

Each PE adds one register stage per hop, so A[i][k] (fed to row i at t = i + k) reaches column j at t = i + k + j, and B[k][j] (fed to column j at t = j + k) reaches row i at t = j + k + i. Therefore **PE(i,j) sees A[i][k] and B[k][j] at t = i + j + k.**

Values fed per cycle (0 = zero is fed):

| t | row 0 | row 1 | row 2 | row 3 | col 0 | col 1 | col 2 | col 3 |
|---|-------|-------|-------|-------|-------|-------|-------|-------|
| 0 | A00 | 0 | 0 | 0 | B00 | 0 | 0 | 0 |
| 1 | A01 | A10 | 0 | 0 | B10 | B01 | 0 | 0 |
| 2 | A02 | A11 | A20 | 0 | B20 | B11 | B02 | 0 |
| 3 | A03 | A12 | A21 | A30 | B30 | B21 | B12 | B03 |
| 4 | 0 | A13 | A22 | A31 | 0 | B31 | B22 | B13 |
| 5 | 0 | 0 | A23 | A32 | 0 | 0 | B32 | B23 |
| 6 | 0 | 0 | 0 | A33 | 0 | 0 | 0 | B33 |
| 7-9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

The last pair reaches PE(3,3) at t = 9, so a multiplication takes 10 cycles = 3N - 2. `done` goes high the cycle after t = 9. A worked 2x2 example is in `docs/handtrace_2x2.md`.

## 5. Implementation notes

- The code is plain Verilog-2001 (no SystemVerilog) with simple constructs: `always @(posedge clk)`, `generate`/`genvar`, and `+:` part-selects.
- `clear` is a combinational pulse (`start && state != RUN`), so accumulators are already zero when the first product arrives at t = 0, and a `start` during a run is ignored.
- The accumulator width is 20 bits: the maximum value 4 x 255 x 255 = 260100 needs 18 bits, so there is spare room.
- Feeding zeros outside the valid index range is harmless, since 0 x anything = 0.
- The Verilog simulator commands are only in `scripts/run.sh` (Icarus Verilog 0.9.7). The Logisim circuit is built by hand following `docs/logisim_build_guide.md`; Logisim version: [TODO-fill-in-version-used].

## 6. Verification

The testbench `tb/tb_top.v` instantiates `top`, applies a hardcoded or random A and B, pulses `start`, waits for `done` (with a timeout), and compares all 16 C elements to a software triple-loop reference. Each test prints PASS or FAIL, and a final TOTAL line reports how many test groups passed. Tests run back to back without reset. The waveform is saved to `dump.vcd`.

| # | Test | What it proves |
|---|------|----------------|
| 1 | identity (A = I, B = 1..16) | C equals B; row/column indexing and timing are correct |
| 2 | all zeros | no spurious additions; clean accumulators |
| 3 | all ones | every C element is 4; each PE adds exactly 4 products |
| 4 | all 255 | every C element is 260100; the maximum value fits in 20 bits |
| 5 | hand-picked (A = 1..16, B = 16..1) | asymmetric data detects swapped or transposed indices |
| 6 | B identity (A = 1..16, B = I) | C equals A; checks the other side of the dataflow |
| 7 | single hot cell (A[2][1] = 200, B[1][3] = 150) | only C[2][3] = 30000 is non-zero; every product lands in the right PE |
| 8 | random x 50 (fixed seed) | many varied inputs and back-to-back runs without leakage |

Waveform screenshots:

[INSERT SCREENSHOT: docs/waveforms/control_fsm.png] — `clear`, `state`, `t`, `done`.
[INSERT SCREENSHOT: docs/waveforms/pe_2_1.png] — PE(2,1) inputs and accumulator showing A[2][k] and B[k][1] meeting at t = 3 + k.

## 6a. Logisim implementation

The Verilog design is the verified reference model. The same design is drawn by hand in Logisim so it can be shown as a circuit.

| Verilog | Logisim part |
|---------|--------------|
| `pe.v` | `PE` subcircuit: two Bit Extenders (8 to 20 bits), 20-bit Multiplier, 20-bit Adder, 20-bit `acc` Register, two 8-bit Registers (`a_out`, `b_out`) |
| `systolic_array.v` | 4x4 grid of `PE` subcircuits; the links are wires |
| `control.v` state and counter | `run` Register, 4-bit Counter `t`, Comparator `t = 10` (= `done`), five gates |
| `control.v` feeder | 8 ROMs addressed by `t`, with i delay Registers on row i and j on column j |
| `A_flat`, `B_flat` | ROM contents, loaded from images made by `logisim/make_rom.py` |
| `clear` | `Start AND NOT run`, to the Clear pins |
| `done` | Comparator output |
| `top.v` | `main` circuit |

Main design points:

- **Unskewed ROMs plus delay registers.** Each ROM lists a row of A (or a column of B) in order, and a counter `t` addresses all of them. A register delays by one clock, so i registers turn A[i][t] into A[i][t-i], which is the Verilog feeder rule. Zeros after the last element come from the unused ROM words, and cleared registers give zeros before the data starts.
- **20-bit multiplier.** A Logisim Multiplier keeps only as many bits as its width, so the 8-bit inputs are zero-extended to 20 bits first. The low 20 bits then hold the whole product.
- **Control.** `run` is set by Start, the counter counts while `run` and not `done`, and `done` is `t = 10`. The counter stops at 10, so it does not wrap.
- **Procedure.** Load the 8 ROM images of a case, press Start, tick 11 times (one start tick and 10 run ticks), and compare the 16 probes with the expected C printed by `make_rom.py` (also in `logisim/test_cases.md`).

Logisim test cases: paper 2x2 example, identity, B identity, all ones, all 255, hand-picked (A = 1..16, B = 16..1) and a fixed-seed random case. Results: [INSERT Logisim results: fill in the "Logisim OK?" column of `logisim/test_cases.md` after running each case]. [INSERT SCREENSHOT: docs/logisim/main_circuit.png] and [INSERT SCREENSHOT: docs/logisim/hand_picked_result.png].

## 7. Results

All 8 test groups pass: `TOTAL: 8 of 8 test groups passed`. A multiplication takes 10 clock cycles from the cycle after `start` to `done`. [INSERT any extra results, e.g. synthesis area or maximum clock frequency, if measured with the course tools.]

| Parameter | Value |
|-----------|-------|
| Array size | 4 x 4 |
| Input width | 8-bit unsigned |
| Accumulator width | 20 bits |
| Latency | 10 cycles (3N - 2) |
| PEs | 16 |
| Multipliers | 16 (one per PE) |

## 8. Limitations and future work

- **Fixed size**: the grid is hardcoded to 4x4. Making N a parameter would let the same code scale; for N = 8 the counter needs 5 bits, latency is 22 cycles, and 20-bit accumulators still suffice.
- **Unsigned only**: signed operands would need signed multipliers.
- **No pipelined output**: C is only valid when `done` is high; results are not streamed out or overlapped with the next multiplication.
- **Scaling**: large N needs many multipliers and wide buses; bigger matrices would be split into 4x4 blocks.
- **Overflow**: no overflow detection; not needed here, but a larger N or wider inputs would require wider accumulators.

## 9. Conclusion

A 4x4 output-stationary systolic matrix multiplier was designed in Verilog-2001 with a very simple controller that needs no skew buffers. The timing rule t = i + j + k explains exactly when each PE receives its operands, and the 10-cycle latency matches 3N - 2. The design passes all directed and random tests against a software reference. The code and documentation are kept simple so that every line can be explained.
