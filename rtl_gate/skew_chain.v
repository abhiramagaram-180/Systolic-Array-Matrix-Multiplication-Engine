// Delay line: STAGES registers in a row. The output is the input delayed by
// STAGES clock cycles. Row i of A and column j of B use i and j stages, so
// row i starts i cycles late and column j starts j cycles late.
// clear = 1 sets every stage to 0 on the next clock edge.
module skew_chain #(
    parameter W      = 4,
    parameter STAGES = 1
) (
    input          clk,
    input          clear,
    input  [W-1:0] din,
    output [W-1:0] dout
);

    wire [(STAGES+1)*W-1:0] stage;      // stage[s*W +: W] is the value after s registers

    assign stage[0 +: W] = din;             // wiring only
    assign dout = stage[STAGES*W +: W];     // wiring only

    genvar s;
    generate
        for (s = 0; s < STAGES; s = s + 1) begin : delay_stage
            reg_n #(.N(W)) u_reg (
                .clk   (clk),
                .clear (clear),
                .d     (stage[s*W +: W]),
                .q     (stage[(s+1)*W +: W])
            );
        end
    endgenerate

endmodule
