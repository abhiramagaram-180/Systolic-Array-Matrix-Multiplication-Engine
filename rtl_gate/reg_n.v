// N-bit register with synchronous clear.
// Every bit is a D flip-flop. In front of each flip-flop there is an AND gate:
//   d_gated = d AND (NOT clear)
// so when clear = 1 the flip-flop loads 0 on the next clock edge.
// Gates: 1 NOT + N AND (+ N flip-flops).
module reg_n #(
    parameter N = 4
) (
    input          clk,
    input          clear,
    input  [N-1:0] d,
    output [N-1:0] q
);

    wire         not_clear;
    wire [N-1:0] d_gated;

    not g_inv (not_clear, clear);

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : bit_slice
            and g_and (d_gated[i], d[i], not_clear);
            dff u_dff (.clk(clk), .d(d_gated[i]), .q(q[i]));
        end
    endgenerate

endmodule
