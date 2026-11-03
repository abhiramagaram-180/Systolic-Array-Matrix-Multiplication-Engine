# Hand trace: 2x2 example

A = [[1, 2], [3, 4]], B = [[5, 6], [7, 8]].
Expected C = A x B = [[1*5+2*7, 1*6+2*8], [3*5+4*7, 3*6+4*8]] = [[19, 22], [43, 50]].

For N = 2 the same rules apply: row i is fed A[i][t-i], column j is fed B[t-j][j] (zero outside 0..1), and PE(i,j) sees A[i][k] and B[k][j] at t = i + j + k. The last pair arrives at t = 1+1+1 = 3, so a run is t = 0..3 (4 cycles = 3N - 2).

## What is fed into the array

| t | row 0 (A) | row 1 (A) | col 0 (B) | col 1 (B) |
|---|-----------|-----------|-----------|-----------|
| 0 | A00 = 1 | 0 | B00 = 5 | 0 |
| 1 | A01 = 2 | A10 = 3 | B10 = 7 | B01 = 6 |
| 2 | 0 | A11 = 4 | 0 | B11 = 8 |
| 3 | 0 | 0 | 0 | 0 |

## What each PE receives and holds

For each cycle t: the inputs `a_in`, `b_in` that the PE sees during cycle t, and the value of `acc` **after** the clock edge that ends that cycle (acc starts at 0 because of `clear`). An input of 0 contributes nothing.

### PE(0,0) — holds C[0][0]

| t | a_in | b_in | product | acc after |
|---|------|------|---------|-----------|
| 0 | 1 (A00) | 5 (B00) | 5 | 5 |
| 1 | 2 (A01) | 7 (B10) | 14 | 19 |
| 2 | 0 | 0 | 0 | 19 |
| 3 | 0 | 0 | 0 | 19 |

### PE(0,1) — holds C[0][1]

A arrives from PE(0,0) one cycle late; B comes straight from column 1.

| t | a_in | b_in | product | acc after |
|---|------|------|---------|-----------|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 1 (A00) | 6 (B01) | 6 | 6 |
| 2 | 2 (A01) | 8 (B11) | 16 | 22 |
| 3 | 0 | 0 | 0 | 22 |

### PE(1,0) — holds C[1][0]

A comes straight from row 1; B arrives from PE(0,0) one cycle late.

| t | a_in | b_in | product | acc after |
|---|------|------|---------|-----------|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 3 (A10) | 5 (B00) | 15 | 15 |
| 2 | 4 (A11) | 7 (B10) | 28 | 43 |
| 3 | 0 | 0 | 0 | 43 |

### PE(1,1) — holds C[1][1]

Both inputs arrive one hop late, so the first pair is at t = 2.

| t | a_in | b_in | product | acc after |
|---|------|------|---------|-----------|
| 0 | 0 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 |
| 2 | 3 (A10) | 6 (B01) | 18 | 18 |
| 3 | 4 (A11) | 8 (B11) | 32 | 50 |

## Result

After t = 3 the accumulators hold 19, 22, 43, 50 — exactly [[19, 22], [43, 50]]. ✓

Check against t = i + j + k: PE(1,1) sees k = 0 (A[1][0] and B[0][1]) at t = 1+1+0 = 2 ✓ and k = 1 (A[1][1] and B[1][1]) at t = 1+1+1 = 3 ✓.

## How the 4x4 design extends this

Nothing changes in the idea, only the size:

- The grid is 4 x 4 instead of 2 x 2, so there are 16 PEs.
- Each row/column has 4 values to feed, so k runs 0..3 and the controller feeds A[i][t-i] and B[t-j][j] for indices 0..3.
- The last pair reaches PE(3,3) at t = 3+3+3 = 9, so a run takes 10 cycles (3N - 2 with N = 4).
- Each accumulator sums 4 products instead of 2, which is why it is 20 bits wide.
