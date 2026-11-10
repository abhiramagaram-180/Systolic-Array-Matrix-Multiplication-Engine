# Logisim build guide

This guide shows how to redraw the verified Verilog design (`rtl/`) in Logisim by hand. The Verilog design is the **reference model**: whatever Logisim shows must match the expected C printed by `logisim/make_rom.py`, which uses the same software reference as the Verilog testbench.

Logisim version: **TODO-fill-in-version-used** (Logisim 2.7.1 and Logisim-evolution have the same components; pin positions and a few attribute names can differ slightly. Hover the mouse over any pin to see its name.)

Shortcuts differ slightly in the original Logisim 2.7.1: Ctrl+T = Tick Once (a half cycle), so press it twice. Always check the Simulate menu.

Components used (all from Logisim's standard libraries):

- **Arithmetic**: Adder, Multiplier, Bit Extender, Comparator
- **Memory**: Register, Counter, ROM
- **Wiring**: Pin, Clock, Probe, Splitter, Constant
- **Input/Output**: Button, Hex Digit Display
- **Gates**: AND, OR, NOT (only 5 gates, for the control logic)

## The idea in 6 lines

1. A **PE** (processing element) is a small subcircuit: multiply, add into an accumulator, pass A and B on.
2. The array is a grid of PE subcircuits. A flows right, B flows down.
3. The **ROMs** hold the matrices *unskewed*: row i file has A[i][0], A[i][1], ... at addresses 0, 1, ...
4. A counter `t` addresses the ROMs. **Delay registers** do the skew: row i has i of them, column j has j of them.
5. A delay of i cycles turns "A[i][t]" into "A[i][t-i]", which is exactly what the Verilog feeder computes.
6. `done` is high when `t` reaches 10 (for 4x4).

## Step (a): build the PE subcircuit

1. Menu **Project > Add Circuit**, name it `PE`. You are now editing `PE`.
2. Add these **input pins** (Wiring > Pin, facing east) and label them:
   - `clk` (1 bit), `clear` (1 bit)
   - `a_in` (8 bits), `b_in` (8 bits)
3. Add these **output pins** (Pin with "Output?" = Yes, facing west) and label them:
   - `a_out` (8 bits), `b_out` (8 bits), `acc` (20 bits)
4. Add two **Bit Extenders** (Arithmetic). Set *Bit Width In* = 8, *Bit Width Out* = 20, *Extension Type* = Zero. Connect `a_in` to one and `b_in` to the other.
   - **Why extend first?** A Logisim Multiplier gives an output with the *same width as its inputs* and throws the upper bits away. If the multiplier were 8 bits wide, only the low 8 bits of the 16-bit product would be kept (wrong). With a 20-bit multiplier the low 20 bits contain the whole product, because 255 x 255 = 65025 needs only 16 bits.
5. Add a **Multiplier** (Arithmetic), *Data Bits* = 20. Connect the two extended values to its two inputs. Leave carry-in and carry-out unconnected.
6. Add an **Adder** (Arithmetic), *Data Bits* = 20. Inputs: the multiplier output and the accumulator output (feedback, see next step). Leave carry pins unconnected.
7. Add a **Register** (Memory) named `acc_reg`, *Data Bits* = 20, trigger = rising edge.
   - D input = Adder output.
   - Clock pin = `clk`.
   - Clear pin = `clear` (the Register's *clear* resets it to 0).
   - Q output = `acc` output pin **and** the second Adder input (this is the feedback loop: `acc <= acc + product`).
   - Leave the enable pin unconnected (unconnected means always enabled).
8. Add two **Registers**, *Data Bits* = 8: `a_reg` (D = `a_in`, Q = `a_out`) and `b_reg` (D = `b_in`, Q = `b_out`). Connect both clock pins to `clk` and both clear pins to `clear`.
   - These registers are the "one clock per hop" delay. They are why PE(i,j) sees A[i][k] and B[k][j] at t = i + j + k.

Compare with `rtl/pe.v`: `acc <= acc + product; a_out <= a_in; b_out <= b_in;` and `clear` zeroing all three.

Note on `clear`: in Verilog the clear acts at the next clock edge (synchronous). The Logisim Register clear pin acts immediately while it is 1 (asynchronous). Both give the same result for this design, because clear is only high while the circuit is idle.

## Step (b): test the PE alone

Open the `PE` circuit (double-click it in the left list), choose the Poke tool (hand), and add a Probe on each output if you like (right-click a pin and look at the value is enough).

1. Set `clear` = 1, then back to 0. `acc` = 0.
2. Set `a_in` = 3 and `b_in` = 4 (click the pin to edit; on an 8-bit pin type the value).
3. Press **F9** once (one full clock cycle, one rising edge). Expect `acc` = 12, `a_out` = 3, `b_out` = 4.
4. Press **F9** again. Expect `acc` = 24.
5. Set `clear` = 1 then 0. `acc` back to 0, `a_out` = `b_out` = 0.

If the clock is a `clk` input pin, you can also toggle `clk` 0 -> 1 by clicking it (a rising edge is one tick).

## Step (c): the 2x2 array with manually driven inputs

1. Menu **Project > Add Circuit**, name it `main`. Place four copies of `PE` in a 2x2 grid (click the `PE` circuit in the left list, then click in the canvas).
2. Add a **Clock** (Wiring) and a `clear` input pin. Wire the clock to the `clk` pin of all four PEs and `clear` to the `clear` pin of all four PEs. (If you prefer manual ticking, use a 1-bit input pin as `clk` and toggle it; or press F9 with a Clock component.)
3. Add four 8-bit input pins: `row0`, `row1` (left side) and `col0`, `col1` (top).
4. Wire (this is `systolic_array.v`):
   - `row0` -> PE(0,0).a_in, PE(0,0).a_out -> PE(0,1).a_in
   - `row1` -> PE(1,0).a_in, PE(1,0).a_out -> PE(1,1).a_in
   - `col0` -> PE(0,0).b_in, PE(0,0).b_out -> PE(1,0).b_in
   - `col1` -> PE(0,1).b_in, PE(0,1).b_out -> PE(1,1).b_in
   - Leave `a_out` of PE(0,1), PE(1,1) and `b_out` of PE(1,0), PE(1,1) unconnected.
5. Add four **Probes** (Wiring) on the `acc` outputs and label them `C00`, `C01`, `C10`, `C11`. Right-click a probe, set *Radix* to 10 (decimal).

Run it (set the pins *before* each tick, as the "inputs during cycle t"):

1. `clear` = 1, then 0.
2. Apply each row below, then press F9 once:

| Tick | row0 | row1 | col0 | col1 | C00 | C01 | C10 | C11 after the tick |
|------|------|------|------|------|-----|-----|-----|-----|
| 1 (t=0) | 1 | 0 | 5 | 0 | 5 | 0 | 0 | 0 |
| 2 (t=1) | 2 | 3 | 7 | 6 | 19 | 6 | 15 | 0 |
| 3 (t=2) | 0 | 4 | 0 | 8 | 19 | 22 | 43 | 18 |
| 4 (t=3) | 0 | 0 | 0 | 0 | 19 | 22 | 43 | 50 |

Expected final result: **[[19, 22], [43, 50]]**. This is the table in `docs/handtrace_2x2.md`. If it matches, the PE and the wiring are correct.

## Step (d): the counter, the running flag and `done`

Add this control logic to `main` (it is the FSM of `control.v`):

1. **Start**: an input **Pin** (1 bit) named `Start`. (A **Button** also works with a free-running clock. If you step manually with F9, use a Pin, because you can click it on, tick, and click it off.)
2. **run**: a 1-bit **Register** named `run`. Clock = the clock. Enable unconnected.
3. **t**: a 4-bit **Counter** (Memory), *Data Bits* = 4, *Maximum Value* = 0xF. Clock = the clock. Its enable pin = `busy` (below). Its clear pin = `clear` (below). Its output is `t`.
4. **done**: a **Comparator** (Arithmetic), *Data Bits* = 4, unsigned. Inputs: `t` and a **Constant** of value 10 (hex A, 4 bits; use 4 for the 2x2 build because 3N-2 = 4). Use its **equal** output as `done`. Add an output pin `done` (and a Hex Digit Display on `t` so you can see the cycle number; 10 shows as "A").
5. Five gates:
   - `busy = run AND (NOT done)`
   - `run.D = Start OR busy`
   - `clear = Start AND (NOT run)`
   - Connect `busy` to the counter enable, `run.D` to the D input of `run`, and `clear` to the `clear` pin of every PE, every delay register (step e) and the counter clear.

How it works:

- Idle: `run` = 0, `t` = 0, nothing counts.
- Press Start (`Start` = 1): `clear` = 1, which zeroes the counter, the PEs and the delay registers. On the next tick `run` becomes 1. Set `Start` back to 0.
- While `run` = 1 and `t` < 10, `busy` = 1 and `t` counts 0, 1, 2, ... 10.
- When `t` = 10, `done` = 1, `busy` = 0, so the counter stops at 10 and does not wrap. On the next tick `run` falls back to 0.
- To run again: wait one tick after `done` (so `run` is 0), then press Start.

This matches `control.v` (IDLE -> RUN -> DONE) except that Verilog accepts Start in the DONE state immediately, while here you wait one extra tick.

## Step (e): ROMs and delay registers (2x2 first)

1. Add one **ROM** (Memory) per row and per column: *Address Bit Width* = 4, *Data Bit Width* = 8. For 2x2 you need 4 ROMs: `A_row0`, `A_row1`, `B_col0`, `B_col1` (label each). Connect every ROM address to `t`. Leave chip-select unconnected.
2. Row i delay: after the ROM data output put **i** 8-bit **Registers** in a chain (data out of one -> D of the next). All clocks = the clock, all clear pins = `clear`.
   - Row 0: no register. Row 1: 1 register. (4x4: rows 2 and 3 have 2 and 3.)
   - Column j delay: the same with **j** registers. Column 0: none. Column 1: 1 register.
3. The output of each chain replaces the `row0`, `row1`, `col0`, `col1` input pins from step (c): remove those pins and connect the chain outputs to the PE inputs.
4. Generate the ROM images:

```bash
python logisim/make_rom.py 2 paper_2x2
```

5. Load each image: **right-click a ROM > Load Image...** and choose the matching file in `logisim/roms/paper_2x2/` (`A_row0.hex` into the `A_row0` ROM, etc.). Check with the Poke tool: click the ROM and look at its contents (address 0 and 1 hold the values; the rest are 0).
6. Run: set `Start` = 1, press F9 once, set `Start` = 0, then press F9 four more times. Now `t` = 4, `done` = 1 and the probes show **19, 22, 43, 50**.

### Why the ROMs hold unskewed data

The ROM row i just lists A[i][0], A[i][1], ... and is read with the same address `t` for every row, so the contents are easy to read and check. A register delays its input by one clock, so after i registers the value seen at cycle t is the one read at cycle t-i, i.e. A[i][t-i]. Cleared registers hold 0, so for t < i the row gets zeros, and after the last element the ROM holds zeros. This is exactly the Verilog rule "feed A[i][t-i] if the index is 0..3, otherwise 0".

## Step (f): scale to 4x4

1. Place 16 `PE` subcircuits in a 4x4 grid (build one row, select it, copy and paste).
2. Wiring rule, for every PE(i,j):
   - `a_in`: from PE(i,j-1).a_out, or (for j = 0) from the end of row i's delay chain.
   - `b_in`: from PE(i-1,j).b_out, or (for i = 0) from the end of column j's delay chain.
   - `clk` and `clear` go to every PE.
3. ROMs and delay chains: 4 row ROMs with 0, 1, 2, 3 registers and 4 column ROMs with 0, 1, 2, 3 registers. That is 12 delay registers (8 bits each).
4. Change the done-constant to **10**.
5. Add 16 probes `C00` ... `C33` (radix 10 decimal) on the `acc` outputs.
6. Leave the last column's `a_out` and last row's `b_out` unconnected.

Optional: use a **Splitter** to gather bits only if you want a combined bus; it is not needed for the design to work.

## Step (g): load images, run, and check

Load images: generate the files with `python logisim/make_rom.py 4 hand_picked`, then right-click each of the 8 ROMs > **Load Image...** and pick `A_row0.hex` ... `A_row3.hex` and `B_col0.hex` ... `B_col3.hex` from `logisim/roms/hand_picked/`. (Run `python logisim/make_rom.py all` once to create all of them.)

Run:

- **One full clock cycle at a time**: **F9** = one full clock cycle (one rising edge) (Simulate > Manual Tick Full Cycle). Ctrl+T is a half cycle, so press it twice.
- **Automatic**: Simulate > Tick Frequency (choose e.g. 1 Hz), then Simulate > **Auto Ticks Enabled** (Ctrl+K). Press Start while it runs; turn Auto Ticks Enabled off to freeze the display. (Ctrl+E is Auto propagate, not tick enabling.)

Procedure for each test case:

1. Load the 8 ROM images of the case.
2. `Start` = 1, one tick, `Start` = 0.
3. Ten more ticks. `t` must show 10 (A) and `done` = 1.
4. Compare the 16 probes with the expected C in `logisim/test_cases.md` (and in the output of `make_rom.py`).
5. Tick the "Logisim OK?" column in your own notes.

What to check:

- `done` rises exactly after 10 ticks following the start tick (the same 10-cycle latency as Verilog).
- After `done`, extra ticks do not change C (the inputs are all zero, so every PE adds 0).
- PE(2,1) sees A[2][k] and B[k][1] together at t = 3 + k: put Probes on its `a_in`, `b_in` and watch them as `t` counts.
- Run `all_255`: every C must be 260100 (the largest value; it needs more than 16 bits, so it checks the 20-bit width).
- Run the cases back to back, as the testbench does.

## Troubleshooting

- **Bus widths mismatched**: a red or orange wire or a "width mismatch" means two different bit widths are joined. Check every Register, Adder, Multiplier and Bit Extender attribute (8 bits for A/B/delay, 20 bits for the multiplier, adder and `acc`, 4 bits for `t`).
- **C values wrong but small**: the multiplier is probably 8 bits wide, or the Bit Extender was forgotten. The multiplier truncates its result to its own width.
- **Unknown (blue "x") or error (red "E") values**: an input is unconnected or unclear. Press `clear` once at the start. Make sure the clock reaches every Register and the Counter.
- **Splitter order**: if you use a Splitter to join or split bits, bit 0 is at the top of the splitter by default. Check *Fan Out*, *Bit Width In* and each bit's assignment in the attributes table.
- **Register enable and reset**: the enable pin must be unconnected (or 1) and the clear pin must be wired to `clear`. If a Register never changes, the enable is held 0. If it always shows 0, the clear is stuck at 1 (check `Start` is back at 0 and that `clear = Start AND NOT run`).
- **Counter wrapping**: if `t` goes 10 -> 11 -> ... -> 15 -> 0, the counter enable is not connected to `busy`. The counter must stop at 10.
- **`done` never goes high**: the comparator constant must be 10 for 4x4 (4 for 2x2), 4 bits wide, and you must use the *equal* output.
- **Wrong C after a second run**: wait one tick after `done` before pressing Start, and make sure Start is released (0) before the next ticks.
- **ROM shows zeros**: you did not load the image, or you loaded it into the wrong ROM. Re-do **Load Image...**. Images must be in the "v2.0 raw" format (the first line of the file says so).
- **Nothing happens**: Auto Ticks Enabled is off. Press F9 or turn it on (Ctrl+K).
- **Result off by a cycle shift**: row i must have i delay registers and column j must have j delay registers, no more or fewer. The row delay chain must come *after* the ROM.
