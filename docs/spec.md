# Systolic Array Matrix Multiplier: Spec

## Decisions
- Language: Verilog-2001 only (design and testbench)
- Size: fixed 4x4, C = A x B
- Inputs: 8-bit unsigned. Accumulators: 20-bit
- Output-stationary: PE(i,j) holds C[i][j]
- A flows right, B flows down
- No skew buffers: control.v feeds row i with A[i][t-i] and column j
  with B[t-j][j] when the index is 0..3, otherwise 0
- Matrices are hardcoded in the testbench (no file loading)

## Timing rule
PE(i,j) sees A[i][k] and B[k][j] at cycle t = i + j + k.
Cycles t = 0..9 (10 cycles). done goes high the cycle after t = 9.

## Flat bus indexing
A_flat[(i*4+k)*8 +: 8] = A[i][k]
B_flat[(k*4+j)*8 +: 8] = B[k][j]
C_flat[(i*4+j)*20 +: 20] = C[i][j]

## Modules and ports
pe: clk, rst, clear, a_in[7:0], b_in[7:0], a_out[7:0], b_out[7:0], acc[19:0]
systolic_array: clk, rst, clear, a_row_in[31:0], b_col_in[31:0], c_flat[319:0]
control: clk, rst, start, A_flat[127:0], B_flat[127:0],
         a_row_in[31:0], b_col_in[31:0], clear, done
top: clk, rst, start, A_flat[127:0], B_flat[127:0], C_flat[319:0], done

## FSM (control.v)
IDLE -> (start) RUN -> (t == 9) DONE -> (start) RUN
clear pulses for one cycle on start; accumulators reset to 0.

## Tool note
The Verilog design is the verified reference model. It is simulated with
Icarus Verilog 0.9.7. The circuit is also redrawn by hand in Logisim
(version TODO-fill-in-version-used); see "Logisim implementation" below.
For the Verilog: Use only basic Verilog-2001: plain
always @(posedge clk), generate/genvar, +: part-selects. No SystemVerilog,
no $clog2, no always_ff/logic, no ANSI-style tricks beyond simple port lists.

## Logisim implementation
The Logisim circuit must give the same results as the Verilog reference model.
Same size (4x4), widths (8-bit inputs, 20-bit accumulators), dataflow and
timing rule (PE(i,j) sees A[i][k] and B[k][j] at t = i + j + k), and the same
10-cycle latency; done goes high when t = 10.

Differences in how it is built (the behaviour is the same):
- The skew is made by delay registers: ROMs hold the UNSKEWED rows of A and
  columns of B (address t holds element t, zeros from address N up to 15), row i
  has i 8-bit delay registers and column j has j of them. A delay of i cycles
  turns A[i][t] into A[i][t-i].
- The multiplier is 20 bits wide, and a and b are zero-extended from 8 to 20 bits
  first, because a Logisim multiplier keeps only as many low bits as its width.
- clear = Start AND NOT run; it uses the asynchronous Clear pin of the Registers
  and the Counter. A new Start is accepted one tick after done.
- The ROM images are made by logisim/make_rom.py; the build steps are in
  docs/logisim_build_guide.md.

Mapping: pe.v = PE subcircuit; systolic_array.v = 4x4 grid of PE subcircuits;
control.v = run Register + Counter t + Comparator (t == 10) + ROMs + delay
registers; top.v = main circuit.
