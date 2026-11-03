# `pe.v`, `systolic_array.v` and `top.v` explained

## `rtl/pe.v` — one processing element

A PE does one multiply-accumulate per clock and passes its inputs along.

```verilog
wire [15:0] product;
assign product = a_in * b_in;
```

8 bits x 8 bits needs up to 16 bits, so `product` is 16 bits. This is plain combinational logic.

```verilog
always @(posedge clk) begin
    if (rst || clear) begin
        acc   <= 20'd0;
        a_out <= 8'd0;
        b_out <= 8'd0;
    end else begin
        acc   <= acc + product;
        a_out <= a_in;
        b_out <= b_in;
    end
end
```

- **`rst`** (reset) and **`clear`** do the same thing inside the PE: set the accumulator and both output registers to 0. `rst` is the global reset at power-up; `clear` is a one-cycle pulse sent before each new multiplication. Clearing `a_out`/`b_out` too makes sure no old data from the last run is still travelling through the array.
- Otherwise, every clock: add the new product to `acc` (this is where C[i][j] is built up), and copy `a_in` to `a_out` and `b_in` to `b_out`. The copy is a register, so the neighbour gets the value **one clock later**. That one-cycle delay per hop is what the timing rule t = i + j + k relies on.
- `acc` is 20 bits: the largest sum is 4 x 255 x 255 = 260100, which fits (it needs 18 bits; 20 is spare room).
- The design is "output-stationary": `acc` stays in the PE; it is the final C[i][j].

## `rtl/systolic_array.v` — the 4x4 grid

### Ports

`a_row_in` is 4 bytes (one per row, entering from the left). `b_col_in` is 4 bytes (one per column, entering from the top). `c_flat` is the 16 accumulators of 20 bits each, packed as C[i][j] at `(i*4+j)*20 +: 20`.

### `a_link` and `b_link`

The PEs are connected through two long wires, each 160 bits = 20 bytes.

**`a_link`**: 4 rows x 5 entries. Entry number `i*5 + j` is the A value **entering PE(i,j)**. Entry `i*5 + j + 1` is what PE(i,j) sends out, which is the input of PE(i,j+1). Entry `i*5 + 0` is the row input from outside. Entry `i*5 + 4` is the output of the last PE in the row and is not used.

**`b_link`**: 5 rows x 4 entries. Entry number `i*4 + j` is the B value **entering PE(i,j)**. PE(i,j) sends its B to entry `(i+1)*4 + j`, which is the input of PE(i+1,j). Entries `0..3` are the column inputs from outside; entries `16..19` (below the last row) are unused.

Small ASCII diagram of the top-left 2x2 corner (the `a_link[x]` / `b_link[x]` labels are entry numbers):

```
                 b_col_in[0]            b_col_in[1]
                 = b_link[0]            = b_link[1]
                     |                      |
                     v                      v
a_row_in[0] --> +---------+ a_link[1]  +---------+ a_link[2]
= a_link[0]     | PE(0,0) | ---------> | PE(0,1) | ----------> ...
                +---------+            +---------+
                     | b_link[4]            | b_link[5]
                     v                      v
a_row_in[1] --> +---------+ a_link[6]  +---------+ a_link[7]
= a_link[5]     | PE(1,0) | ---------> | PE(1,1) | ----------> ...
                +---------+            +---------+
                     | b_link[8]            | b_link[9]
                     v                      v
                    ...                    ...
```

Check with the formulas: PE(1,0) has a_in = a_link[1*5+0] = a_link[5], and its a_out goes to a_link[6]. PE(1,1) has a_in = a_link[6]. PE(1,0) has b_in = b_link[1*4+0] = b_link[4]; PE(0,0) sends its B out to b_link[(0+1)*4+0] = b_link[4]. ✓

Each entry is 8 bits, so entry `x` is the slice `[x*8 +: 8]`.

### `genvar` and `generate`

`genvar i; genvar j;` declare loop variables that exist only while the hardware is being built (not at run time). A `generate ... for` loop stamps out copies of hardware:

1. First loop: connects `a_row_in[i*8 +: 8]` to `a_link[(i*5)*8 +: 8]` for each row (left edge).
2. Second loop: connects `b_col_in[j*8 +: 8]` to `b_link[j*8 +: 8]` for each column (top edge).
3. Third (nested) loop: creates the 16 `pe` instances. The loop labels (`pe_row`, `pe_col`) give each instance a unique name, e.g. `pe_row[2].pe_col[1].u_pe`, which is useful in the waveform viewer.

Each instance connects `a_in`, `a_out`, `b_in`, `b_out` to the right slices of the link wires, and its `acc` to the slice of `c_flat` for C[i][j].

## `rtl/top.v` — the top module

`top` only connects two blocks:

- `control` (`u_control`) takes `start`, `A_flat`, `B_flat` and produces `a_row_in`, `b_col_in`, `clear` and `done`.
- `systolic_array` (`u_array`) takes `a_row_in`, `b_col_in`, `clear` and produces `C_flat`.

The internal wires `a_row_in`, `b_col_in` and `clear` carry signals between the two. There is no other logic. The testbench instantiates `top`.
