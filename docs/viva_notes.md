# Viva notes: 25 likely questions

## Concept

**1. What is a systolic array?**
A grid of simple identical processing elements (PEs). Data is pumped through it rhythmically, one step per clock, and each PE only talks to its neighbours. Like blood pumped by a heart, hence "systolic".

**2. What does "output-stationary" mean?**
The results stay in place: PE(i,j) holds C[i][j] in its accumulator for the whole run, while the inputs A and B move past it. (The other choices keep A or B stationary instead.)

**3. Where does data reuse come from?**
Each A value is used by every PE in its row (4 times) and each B value by every PE in its column (4 times), but it is read from memory/the input bus only once. The PEs pass it on to each other instead of re-reading it.

**4. Why use a systolic array for matrix multiplication?**
It does 16 multiply-accumulates in parallel, has only short local wires, a regular layout that is easy to scale, and a simple controller.

## Design choices

**5. Why 8-bit unsigned inputs?**
It keeps the multipliers small and the testing simple. Unsigned avoids sign handling. (Signed numbers would be a future extension.)

**6. Why 20-bit accumulators?**
The largest possible C element is 4 x 255 x 255 = 260100. That needs 18 bits (2^18 = 262144). 20 bits is safe with spare room, and it would still be enough up to N = 16 (16 x 65025 = 1,040,400 < 2^20 = 1,048,576).

**7. Why no skew buffers?**
Normally the inputs are delayed with registers so that row i is i cycles late. Here the controller just starts row i at t = i and column j at t = j (feeding zeros before that), so no extra buffer hardware is needed.

**8. Why feed A to the right and B down?**
So that A[i][k] meets B[k][j] at PE(i,j): A travels along row i, B travels along column j, and the only PE on both paths is PE(i,j).

## Timing

**9. What is the latency?**
10 cycles for N = 4, which is 3N - 2 (t = 0..9). `done` is high the cycle after t = 9.

**10. Why 3N - 2?**
The last PE, PE(N-1,N-1), receives its last pair at t = (N-1)+(N-1)+(N-1) = 3N - 3. Counting cycles from t = 0, that is 3N - 2 cycles.

**11. Why does PE(i,j) see A[i][k] and B[k][j] at t = i + j + k?**
A[i][k] is fed to row i at t = i + k and takes j one-cycle hops to reach column j. B[k][j] is fed to column j at t = j + k and takes i hops to reach row i. Both arrive at i + j + k.

**12. Why one cycle per hop?**
Each PE registers its outputs (`a_out <= a_in`, `b_out <= b_in`), so the neighbour sees the value one clock later.

## Code

**13. What does each module do (one sentence each)?**
- `pe`: multiply-accumulate and pass A right and B down.
- `systolic_array`: instantiates and wires the 4x4 grid of PEs.
- `control`: FSM and counter that feed the right values at the right time and raise `done`.
- `top`: connects control and array.

**14. What do `rst` and `clear` do?**
`rst` is the global reset: it puts the FSM in IDLE and zeros every PE. `clear` is a one-cycle pulse when `start` is accepted; it zeros the accumulators and the pass-through registers of all PEs so each run starts clean.

**15. Why is `clear` a combinational pulse (`start && state != RUN`)?**
So the accumulators are already zero in the first RUN cycle (t = 0) and the first product is not lost. It also ignores `start` while a run is in progress.

**16. Why is feeding zeros harmless?**
A zero times anything is zero, and adding zero changes nothing. Before a row/column starts and after it ends, zeros flow through the PEs without changing the accumulators.

**17. How are the matrices packed into buses?**
Flat buses with bytes in row-major order: A[i][k] at `(i*4+k)*8 +: 8`, B[k][j] at `(k*4+j)*8 +: 8`, C[i][j] at `(i*4+j)*20 +: 20`.

**18. What are `generate` and `genvar`?**
A way to create many copies of hardware with a loop at elaboration time. `genvar` is the loop variable; it does not exist at run time. Here it creates the 16 PEs and the edge connections.

## Testing

**19. How does the testbench compute the expected value?**
With a plain triple loop in software: for each i, j it sums A[i][k] x B[k][j] over k, then compares with the 20-bit slice of `C_flat` using `!==`. Any difference prints a mismatch line and the test prints FAIL.

**20. What does each test prove?**
- identity (A = I): the result equals B, so rows/columns and indexing are correct.
- B identity: the result equals A, same check from the other side.
- all zeros: nothing is added by mistake, and accumulators were cleared.
- all ones: every C element is 4, so each PE adds exactly 4 products.
- all 255: every C is 260100, the maximum, so 20 bits are enough and nothing overflows.
- hand-picked (1..16 and 16..1): an asymmetric case that detects transposed or swapped indices.
- single hot cell: only C[2][3] = 30000 is non-zero, so every product lands in the correct PE and nowhere else.
- random x 50: 50 random matrix pairs (fixed seed, repeatable); also checks that back-to-back runs do not leak data between runs.

**21. How would I verify the timing in the waveform?**
Open `dump.vcd` in GTKWave. Show `clk`, `start`, `clear`, `u_control.state`, `u_control.t`, `done`. Check that `clear` is high for one cycle on `start`, `t` counts 0..9, and `done` rises the cycle after t = 9. Then add PE(2,1)'s `a_in`, `b_in` and `acc` and check A[2][k] and B[k][1] show up together at t = 3 + k. (Do this once and take screenshots for the report.)

**22. Why a fixed seed in the random test?**
So the run is repeatable: the same inputs every time, and a failure can be reproduced.

**23. Does the testbench test back-to-back runs?**
Yes. Tests run one after another without a reset, so each starts from the DONE state; this checks that `clear` really erases the previous result.

**24. How would the design scale to N = 8?**
Change the grid to 8 x 8 (64 PEs) and the loop bounds and bus widths (A/B buses 512 bits, C bus 64 x 20 bits). The counter must count to 3N - 3 = 21, so it needs 5 bits. Latency becomes 22 cycles. The accumulator needs 8 x 65025 = 520200 < 2^20, so 20 bits still works. The PE does not change at all.

**25. What are the limitations?**
Fixed size 4x4, unsigned only, the whole result is available only at the end (no streaming output), and no overflow detection (it cannot overflow at this size).
