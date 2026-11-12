# What was added in `main_4X4_auto`

File: `logisim/systolic_4x4_auto.circ` (open with Logisim-evolution v5.0.0).

It contains your three original circuits **unchanged** (`main`, `PE`, `main_4X4`) plus one new circuit, **`main_4X4_auto`**. It is a copy of `main_4X4` with a control block added, so the array runs by itself after you press Start. Your original `dlcdPROJECT.circ` was not touched. The project's "main circuit" setting still points at the old `main`, so double-click `main_4X4_auto` in the circuit list to open it.

The ROMs already hold the `hand_picked` case (A = 1..16, B = 16..1). Expected result: `[[80,70,60,50],[240,214,188,162],[400,358,316,274],[560,502,444,386]]`.

## The idea in one paragraph

A counter `t` counts the clock cycles of one run (0 to 10). It addresses all 8 ROMs, so row i of A and column j of B come out in order. The delay registers that were already in your circuit (0, 1, 2, 3 per row and column) turn that into the skewed feed the array needs. A small `run` flag remembers that a run is in progress. When `t` reaches 10, `done` goes high and the counter stops. `clear` wipes the array before a run starts.

## The control signals

| Signal | Meaning | Formula |
|---|---|---|
| `Start` | Input pin you click | (input) |
| `run` | 1-bit Register: a run has started and not yet been cleaned up | next `run` = `Start` OR `busy` |
| `done` | `t` equals 10 | Comparator output (`t` = 0xA) |
| `busy` | A run is in progress | `run` AND (NOT `done`) |
| `clear` | Wipes accumulators, delay registers and `t` | `Start` AND (NOT `run`) |

Why they behave:

- **Idle:** `run` = 0, so `clear` = `Start`. Click Start to 1 and everything is held at 0.
- **Start edge:** at the first clock rising edge with Start = 1, `run` becomes 1. `clear` falls (because `run` = 1), and `t` is still 0.
- **Running:** `busy` = 1 enables the counter, so `t` goes 1, 2, 3 ... 10 on each rising edge. The array accumulates.
- **Done:** at `t` = 10, `done` = 1, `busy` = 0, the counter stops at 10 (it cannot wrap), and C is final. With Start released, `run` falls on the next edge.
- **Run again:** wait one clock after `done`, then click Start again.

## Everything that was added or changed (all inside `main_4X4_auto`)

### 0. Repair of a short in the original (not in your list, needed)

In the original `main_4X4`, the **clear** line (x = 2400) ran straight through the **clk** port of PE22 at (2400,1730). That joined the `clk` net and the `clear` net into one net, so with the old pins the clock and clear were electrically the same wire. With a real control block (clear is driven by a gate, clk by the Clock) it gives errors.

In `main_4X4_auto` only, I removed three wires: (2400,1470)-(2400,1730), (2400,1730)-(2400,1750) and (2400,1470)-(2420,1470). I added: (2400,1470)-(2410,1470), (2410,1470)-(2420,1470), (2410,1470)-(2410,1750), (2410,1750)-(2400,1750). Now `clear` goes down x = 2410 (crossing, not touching, the wire at y = 1510) and reaches the PE22 clear port at (2400,1750) without touching the clk port. The original `main_4X4` still has the short.

### 1. The 8 pins were removed and the gaps joined

Removed Pins `row0..row3` and `col0..col3`, which were manual inputs sitting between the ROM outputs and the data path (their ROM wires ended on the pin body, so they were not even connected). New plain wires:

| Joins | New wire(s) |
|---|---|
| row0 ROM -> PE00 `a_in` | (1070,1220)-(1130,1220). The old stub (1130..1150,1220) was left in place and continues the line |
| row1 ROM -> delay register | (1070,1490)-(1150,1490) |
| row2 ROM -> delay chain | (1070,1770)-(1150,1770) |
| row3 ROM -> delay chain | (1070,2080)-(1150,2080) |
| col0 ROM -> PE00 `b_in` | (1520,750)-(1600,750) |
| col1 ROM -> delay register | (1920,750)-(2000,750) |
| col2 ROM -> delay chain | (2300,750)-(2380,750) |
| col3 ROM -> delay chain | new route: (2650,370)-(2650,750)-(2810,750) |

### 2. `clk` Pin replaced by a Clock

A **Clock** component labelled `clk` now sits at (1220,1050), where the old `clk` pin was, on the same net. A short wire (1220,1050)-(1220,1000)-(1180,1000) gives that net a Tunnel named `clk` so the control block can use it.

### 3. `clear` Pin removed

At (1220,1120) there is now a Tunnel named `clear` on the old wire. The only driver of the `clear` net is the AND gate described below.

### 4. The new control block (top-left of the canvas, x 130-1130, y 120-870)

| Part (label) | Where | What it does and how it is connected |
|---|---|---|
| Input Pin `Start` | (160,240) | You click it. Goes to the OR gate and the `clear` AND gate. |
| OR gate `run_D_or` | (300,260) | `Start` OR `busy` -> D input of `run`. `busy` arrives from a Tunnel. |
| Register `run` (1 bit) | (400,230) | D from the OR gate, clock from Tunnel `clk`, enable tied to a Constant 1 at (360,280) (same style as your other registers). Output Q goes to NOT `run` and the `busy` AND gate. |
| NOT gate `not_run` | (600,260) | Inverts `run` -> second input of the `clear` AND gate. |
| AND gate `clear_and` | (700,180) | `Start` AND NOT `run` -> Tunnel `clear`. |
| NOT gate `not_done` | (560,440) | Inverts `done` (from Tunnel `done`). |
| AND gate `busy_and` | (700,400) | `run` AND NOT `done` -> Tunnel `busy`. |
| Counter `t_counter` | (900,520) | 4 bits, maximum 0xF, classic look. Enable = Tunnel `busy`, clock = Tunnel `clk`, clear = Tunnel `clear`. Output Q -> Tunnel `t`. Load, up/down and data inputs unused. |
| Comparator | (900,720) | 4-bit **unsigned**. Input A = Tunnel `t`, input B = Constant 0xA (4 bits). The "=" output is `done` (Tunnel `done`). |
| Output Pin `done` and LED `done_led` | (1000,780), (1000,840) | Show `done`. |
| Hex Digit Display `t_display` | (1100,520) | Shows `t` (10 shows as A). Fed from a Tunnel `t`. |

### 5. Tunnels

Named tunnels connect nets that are far apart:

| Tunnel | Width | Used for |
|---|---|---|
| `t` | 4 bits | Counter output -> comparator, hex display and all 8 ROM address inputs |
| `clk` | 1 | Clock -> `run` register, counter, (and the array through the old wire) |
| `clear` | 1 | AND gate output -> array (via the tunnel at (1220,1120)) and counter clear |
| `busy` | 1 | `busy_and` output -> OR gate and counter enable |
| `done` | 1 | Comparator "=" -> `not_done`, output pin and LED |

ROM address ports are at the ROM location + (0,10). Each of the 8 ROMs has a 40-pixel wire going left to a 4-bit Tunnel `t`: row ROMs at (620,1060), (640,1390), (640,1690), (640,2020); column ROMs at (1280,350), (1690,310), (2030,340), (2410,310).

### 6. ROM contents

Loaded from `logisim/roms/hand_picked/`: `A_row0..3.hex` into the row ROMs (top to bottom) and `B_col0..3.hex` into the column ROMs (left to right). To change case, right-click each ROM > Load Image, or regenerate with `make_rom.py`.

### 7. Probes labelled

The 16 probes are labelled `C00 ... C33` by following each probe's wire back to its PE's `acc` output (PE label `PEij` gives `Cij`). Probe `C00` already had this label.

## How to use it in Logisim (demo)

1. Open `main_4X4_auto`. Check the ROMs hold the case you want.
2. Click the `Start` pin to 1 (clear is now active and everything is 0).
3. Tick the clock once (**F9**, or turn Auto Ticks on with Ctrl+K). `run` becomes 1.
4. Click `Start` back to 0. Keep ticking. `t` counts 1 ... A. After the 10th tick `done` lights up and the probes show C.
5. To run again: tick once more (so `run` falls), click Start to 1, tick, release, and so on.

## What was verified (headless, Logisim-evolution v5.0.0)

- Test-vector runs on a throwaway copy of `main_4X4_auto` (the Clock replaced by an input pin, the probes by output pins). For each case: Start = 1 for one clock cycle, then 10 more cycles, checking that `done` is 0 until the 10th rising edge and that all 16 C values match. A second run follows with no reset (this tests `clear`). Cases: identity, b_identity, all_ones, all_255 (every cell 260100), hand_picked, random. 48 of 48 vector rows passed for every case. A deliberately wrong expected value was correctly rejected.
- A second throwaway copy kept the **real Clock** component with Start tied to 1 and ran in tty mode until `done`: the final values matched for all six cases, and `done` first rose at step 10.

Not verified: how the canvas looks (overlaps, spacing); clicking and typing in the GUI; loading the ROM images with Load Image (the contents are already embedded in the file).
