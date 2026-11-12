# `rtl/control.v` explained

## The idea in plain language

The array has no extra buffers to line up the data. Instead the controller simply *starts each row and column at the right moment*.

Think of PE(i,j). It needs A[i][k] and B[k][j] **at the same time**, for k = 0, 1, 2, 3.

- A[i][k] enters the array at the left of row i, then moves one PE to the right per clock. To reach column j it needs j extra cycles.
- B[k][j] enters at the top of column j, then moves one PE down per clock. To reach row i it needs i extra cycles.

If row i is fed A[i][k] at cycle `i + k` and column j is fed B[k][j] at cycle `j + k`, then:

- A[i][k] reaches PE(i,j) at cycle `i + k + j`
- B[k][j] reaches PE(i,j) at cycle `j + k + i`

Same cycle. So **row i starts i cycles late** (its first value A[i][0] is fed at t = i) and **column j starts j cycles late** (B[0][j] is fed at t = j). This is what the spec says: row i is fed A[i][t-i] and column j is fed B[t-j][j] whenever that index is 0..3, otherwise 0.

## Walking through the code

### Ports

- `start` begins a multiplication. `A_flat` and `B_flat` are the two matrices packed into 128-bit buses (16 bytes each).
- `a_row_in` (32 bits) is 4 bytes, one per row. `b_col_in` is 4 bytes, one per column.
- `clear` tells the PEs to reset their accumulators. `done` says the result is ready.

### State encoding

```verilog
localparam IDLE = 2'd0;
localparam RUN  = 2'd1;
localparam DONE = 2'd2;
```

Three named numbers for the three states. `state` is a 2-bit register holding one of them.

### The FSM

```
IDLE --start--> RUN --(t == 9)--> DONE --start--> RUN
```

- **IDLE**: waiting after reset. `t` is held at 0. When `start` is 1, go to RUN.
- **RUN**: `t` goes up by 1 every clock. When `t` is 9 (the 10th cycle), go to DONE.
- **DONE**: result is ready, `done` is 1. A new `start` goes back to RUN.
- `rst` forces IDLE and `t = 0`.

Everything is in one `always @(posedge clk)` block, so state and `t` change only on clock edges.

### The `t` counter

`t` counts the cycles of one run: 0, 1, 2, ..., 9. That is 10 cycles = 3N - 2 for N = 4. Cycle 9 is when the last PE, PE(3,3), gets its last pair (3+3+3 = 9).

### The `clear` pulse

```verilog
assign clear = start && (state != RUN);
```

When `start` is 1 in IDLE or DONE, `clear` is 1 during that same cycle. At the next clock edge the PEs reset their accumulators to 0, and at that same edge the state becomes RUN with `t = 0`. So in the very first RUN cycle the accumulators are already 0 and the first product (A[0][0] x B[0][0]) is not lost. The `state != RUN` part means a `start` while running is ignored.

### `done`

```verilog
assign done = (state == DONE);
```

At the end of cycle t = 9 the last accumulate happens at the clock edge, and the state becomes DONE. So `done` goes high the cycle after t = 9, exactly when C is final.

### The feeder loop

```verilog
always @(state or t or A_flat or B_flat) begin
    a_row_in = 32'd0;
    b_col_in = 32'd0;
    if (state == RUN) begin
        for (n = 0; n < 4; n = n + 1) begin
            k = t - n;
            if (k >= 0 && k <= 3)
                a_row_in[n*8 +: 8] = A_flat[(n*4 + k)*8 +: 8];
            if (k >= 0 && k <= 3)
                b_col_in[n*8 +: 8] = B_flat[(k*4 + n)*8 +: 8];
        end
    end
end
```

This block is combinational: whenever `state`, `t`, `A_flat` or `B_flat` changes it recomputes the outputs.

1. Start with all zeros (so anything not set below is 0, and outside RUN everything is 0).
2. For each n from 0 to 3, compute `k = t - n`.
3. If `k` is a valid index (0..3):
   - Row n gets A[n][k]. In the flat bus A[i][k] is at `(i*4+k)*8 +: 8`, so with i = n this is `(n*4 + k)*8`.
   - Column n gets B[k][n]. B[k][j] is at `(k*4+j)*8 +: 8`, so with j = n this is `(k*4 + n)*8`.
4. The same `k = t - n` is used for both because row n and column n both start n cycles late.

`+: 8` means "8 bits starting at this position".

## Cycle-by-cycle table (t = 0..9)

Each cell is the value fed in that cycle ("0" means zero is fed because the index is outside 0..3).

| t | row 0 | row 1 | row 2 | row 3 | col 0 | col 1 | col 2 | col 3 |
|---|-------|-------|-------|-------|-------|-------|-------|-------|
| 0 | A00 | 0 | 0 | 0 | B00 | 0 | 0 | 0 |
| 1 | A01 | A10 | 0 | 0 | B10 | B01 | 0 | 0 |
| 2 | A02 | A11 | A20 | 0 | B20 | B11 | B02 | 0 |
| 3 | A03 | A12 | A21 | A30 | B30 | B21 | B12 | B03 |
| 4 | 0 | A13 | A22 | A31 | 0 | B31 | B22 | B13 |
| 5 | 0 | 0 | A23 | A32 | 0 | 0 | B32 | B23 |
| 6 | 0 | 0 | 0 | A33 | 0 | 0 | 0 | B33 |
| 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Row i uses A[i][t-i]; column j uses B[t-j][j].

## Why PE(i,j) sees A[i][k] and B[k][j] at t = i + j + k

Every PE has a register on its A output and on its B output (`a_out <= a_in`, `b_out <= b_in`). So each hop to the right (for A) or down (for B) costs exactly **one clock cycle**.

- A[i][k] is fed into row i at t = i + k. It then makes j hops to reach column j, so it arrives at t = i + k + j.
- B[k][j] is fed into column j at t = j + k. It makes i hops to reach row i, so it arrives at t = j + k + i.

Both equal `i + j + k`. Example: PE(2,1), k = 3. A[2][3] is fed to row 2 at t = 5 (table above); one hop later it is at PE(2,1) at t = 6. B[3][1] is fed to column 1 at t = 4; two hops later it is at PE(2,1) at t = 6. Both at t = 2 + 1 + 3 = 6. ✓

The zeros fed outside the valid range are harmless: the PE multiplies by 0 and adds 0.

## Controller Clock-Level Operation

### Starting a multiplication

1. The controller remains in IDLE while start is LOW.
2. When start becomes HIGH, clear is asserted.
3. At the next rising clock edge, all PE accumulators and forwarding registers are cleared.
4. The FSM enters RUN.
5. The feeder supplies the first set of matrix elements.

### During computation

- The cycle counter increments on every rising clock edge.
- The feeder selects operands based on the current cycle.
- The PEs perform multiplication and accumulation.
- Zero is supplied when an index is outside the valid matrix range.

### Completion

When the previous counter value is 9, the FSM transitions to DONE.

The done output becomes HIGH, indicating that the accumulated matrix result is ready.

### Starting another multiplication

When start is asserted in DONE:

- clear becomes HIGH.
- PE accumulators and forwarding registers are cleared.
- The FSM transitions to RUN.
- The next multiplication begins from cycle zero.

The start input is expected to be a one-clock-cycle pulse.

### Verification requirement

A back-to-back test should perform two different matrix multiplications without asserting reset between them. Both results must match their expected matrix products independently.
