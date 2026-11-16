// Controller: run flag, cycle counter t and the done / clear signals.
//   clear = start AND (NOT run)          wipes the datapath before a run
//   done  = (t == 10)                    the last product is in the accumulators
//   busy  = run AND (NOT done)           a run is in progress (counter enable)
//   run_next = start OR busy             the run flag stays set until done
// rst (synchronous) forces run = 0 and t = 0.
// A new start is accepted one clock after done: while run is still 1 (the
// cycle when done = 1) a start does not clear anything.
//
// Timeline: start edge -> run = 1, t = 0 -> t counts 1..10 (one per edge)
//           -> done = 1 at t = 10 -> next edge run = 0 (if start = 0).
// Gates (all 2-input): 13 here + counter4 (12) = 25; flip-flops: 1 (run) + 4 (counter).
module control (
    input        clk,
    input        rst,
    input        start,
    output [3:0] t,
    output       clear,
    output       done
);

    wire run;           // flip-flop output: a run has been started
    wire not_run;
    wire not_done;
    wire busy;
    wire run_next;
    wire run_d;         // value loaded into the run flip-flop
    wire not_rst;
    wire counter_clear;
    wire [3:0] not_t;   // only bits 0 and 2 are used
    wire done_hi;       // t3 AND NOT t2
    wire done_lo;       // t1 AND NOT t0

    // clear = start AND NOT run
    not g_not_run (not_run, run);
    and g_clear   (clear, start, not_run);

    // done = (t == 10), 10 = 1010 in binary: t3 AND NOT t2 AND t1 AND NOT t0
    not g_nt0 (not_t[0], t[0]);
    not g_nt2 (not_t[2], t[2]);
    and g_done_hi (done_hi, t[3], not_t[2]);
    and g_done_lo (done_lo, t[1], not_t[0]);
    and g_done    (done, done_hi, done_lo);

    // busy = run AND NOT done
    not g_not_done (not_done, done);
    and g_busy     (busy, run, not_done);

    // run_next = start OR busy, and a synchronous reset
    or  g_run_next (run_next, start, busy);
    not g_not_rst  (not_rst, rst);
    and g_run_d    (run_d, run_next, not_rst);
    dff u_run (.clk(clk), .d(run_d), .q(run));

    // cycle counter: counts while busy, cleared by clear or rst
    or g_counter_clear (counter_clear, clear, rst);
    counter4 u_counter (.clk(clk), .clear(counter_clear), .en(busy), .q(t));

endmodule
