// 4-bit synchronous counter built from gates and flip-flops.
// If en = 1 the value goes up by 1 on each clock edge; if en = 0 it holds.
// clear = 1 sets it to 0 on the next clock edge (clear wins over en).
//
// Incrementer: bit i flips when all lower bits are 1 (and en = 1):
//   toggle[0] = en
//   toggle[1] = en AND q0
//   toggle[2] = en AND q0 AND q1
//   toggle[3] = en AND q0 AND q1 AND q2
//   next[i]   = q[i] XOR toggle[i]
// Gates: 3 AND + 4 XOR (+ the 4-bit reg_n: 1 NOT + 4 AND, 4 flip-flops).
module counter4 (
    input        clk,
    input        clear,
    input        en,
    output [3:0] q
);

    wire [3:0] toggle;      // 1 = this bit flips on the next edge
    wire [3:0] next_value;  // value after incrementing

    assign toggle[0] = en;  // wiring only

    and g_t1 (toggle[1], toggle[0], q[0]);
    and g_t2 (toggle[2], toggle[1], q[1]);
    and g_t3 (toggle[3], toggle[2], q[2]);

    xor g_x0 (next_value[0], q[0], toggle[0]);
    xor g_x1 (next_value[1], q[1], toggle[1]);
    xor g_x2 (next_value[2], q[2], toggle[2]);
    xor g_x3 (next_value[3], q[3], toggle[3]);

    // the four flip-flops, with the synchronous clear
    reg_n #(.N(4)) u_reg (.clk(clk), .clear(clear), .d(next_value), .q(q));

endmodule
