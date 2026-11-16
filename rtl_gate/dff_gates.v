// OPTIONAL: the same D flip-flop built only from NAND gates (master-slave).
// Used only when compiling with -DUSE_NAND_DFF (see scripts/run_gate.sh).
//
//   master latch: transparent while clk = 0, remembers d when clk rises
//   slave  latch: transparent while clk = 1, copies the master to q
// A latch is two cross-coupled NAND gates with two input gates:
//   n_set   = NAND(d, enable)      n_reset = NAND(NOT d, enable)
//   q       = NAND(n_set,   q_bar) q_bar   = NAND(n_reset, q)
// Gates per flip-flop: 8 NAND (4 per latch) + 2 NOT (one for d, one for the clock) = 10.
// Whole design: 341 flip-flops x 10 = 3410 extra gates (2674 + 3410 = 6084 in total).
`ifdef USE_NAND_DFF
module dff (
    input  clk,
    input  d,
    output q
);

    wire clk_bar;       // inverted clock (master enable)
    wire d_bar;         // inverted data
    wire m_set, m_reset, m_q, m_q_bar;   // master latch
    wire s_set, s_reset, s_q_bar;        // slave latch

    not g_clk (clk_bar, clk);
    not g_d   (d_bar, d);

    // master latch: enabled when clk = 0
    nand g_m1 (m_set,   d,     clk_bar);
    nand g_m2 (m_reset, d_bar, clk_bar);
    nand g_m3 (m_q,     m_set,   m_q_bar);
    nand g_m4 (m_q_bar, m_reset, m_q);

    // slave latch: enabled when clk = 1
    nand g_s1 (s_set,   m_q,     clk);
    nand g_s2 (s_reset, m_q_bar, clk);
    nand g_s3 (q,       s_set,   s_q_bar);
    nand g_s4 (s_q_bar, s_reset, q);

endmodule
`endif
