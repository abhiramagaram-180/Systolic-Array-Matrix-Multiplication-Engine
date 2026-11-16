// D flip-flop: the ONLY behavioural code in the gate-level design.
// On every rising clock edge q takes the value of d.
// Every flip-flop in the design is an instance of this module, so it can be
// swapped for the gate-built version in dff_gates.v (compile with
// -DUSE_NAND_DFF) without touching anything else.
`ifndef USE_NAND_DFF
module dff (
    input      clk,
    input      d,
    output reg q
);

    always @(posedge clk) begin
        q <= d;
    end

endmodule
`endif
