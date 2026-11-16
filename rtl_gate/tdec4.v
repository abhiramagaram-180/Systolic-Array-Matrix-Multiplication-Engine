// Decoder for the cycle counter: turns t into four select lines.
//   sel[k] = 1 when t = k (for k = 0..3), all 0 when t >= 4.
// These lines pick which element the selectors (select4) pass on, so after the
// 4 elements are sent the selectors give 0 (this replaces the zero-filled ROM).
//   lt4      = (NOT t3) AND (NOT t2)                  "t is below 4"
//   low[k]   = decode of the two low bits t1 t0        (k = 0..3)
//   sel[k]   = lt4 AND low[k]
// Gates (all 2-input): 4 NOT + 5 AND + 4 AND = 13.
module tdec4 (
    input  [3:0] t,
    output [3:0] sel
);

    wire [3:0] nt;      // inverted t bits
    wire       lt4;     // 1 when t < 4
    wire [3:0] low;     // one-hot decode of t1 t0

    not g_n0 (nt[0], t[0]);
    not g_n1 (nt[1], t[1]);
    not g_n2 (nt[2], t[2]);
    not g_n3 (nt[3], t[3]);

    and g_lt4  (lt4, nt[3], nt[2]);

    and g_low0 (low[0], nt[1], nt[0]);    // t1 t0 = 00
    and g_low1 (low[1], nt[1], t[0]);     // t1 t0 = 01
    and g_low2 (low[2], t[1],  nt[0]);    // t1 t0 = 10
    and g_low3 (low[3], t[1],  t[0]);     // t1 t0 = 11

    and g_sel0 (sel[0], lt4, low[0]);     // t = 0
    and g_sel1 (sel[1], lt4, low[1]);     // t = 1
    and g_sel2 (sel[2], lt4, low[2]);     // t = 2
    and g_sel3 (sel[3], lt4, low[3]);     // t = 3

endmodule
