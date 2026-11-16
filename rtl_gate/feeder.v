// Feeder: gives the array its inputs, one value per row and per column.
//   1. tdec4 turns the cycle counter t into select lines.
//   2. 4 selectors (one per row) give A[i][t] for t = 0..3 (then 0).
//      4 selectors (one per column) give B[t][j] for t = 0..3 (then 0).
//      This data is NOT skewed.
//   3. Row i then goes through i delay registers and column j through j
//      delay registers (skew_chain), so the array sees A[i][t-i] and B[t-j][j].
// Flat bus indexing: A[i][k] = A_flat[(i*4+k)*W +: W], B[k][j] = B_flat[(k*4+j)*W +: W].
module feeder #(
    parameter W = 4
) (
    input               clk,
    input               clear,
    input  [3:0]        t,
    input  [16*W-1:0]   A_flat,
    input  [16*W-1:0]   B_flat,
    output [4*W-1:0]    a_row_in,
    output [4*W-1:0]    b_col_in
);

    wire [3:0]     sel;         // one-hot select lines for t = 0..3
    wire [4*W-1:0] a_pick;      // unskewed values, one per row
    wire [4*W-1:0] b_pick;      // unskewed values, one per column

    tdec4 u_dec (.t(t), .sel(sel));

    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : lane
            // row i: A[i][0..3] are 4 neighbouring values in A_flat
            select4 #(.W(W)) u_sel_a (
                .sel (sel),
                .din (A_flat[i*4*W +: 4*W]),
                .y   (a_pick[i*W +: W])
            );
            // column i: B[0][i], B[1][i], B[2][i], B[3][i]
            select4 #(.W(W)) u_sel_b (
                .sel (sel),
                .din ({B_flat[(3*4+i)*W +: W], B_flat[(2*4+i)*W +: W],
                       B_flat[(1*4+i)*W +: W], B_flat[(0*4+i)*W +: W]}),
                .y   (b_pick[i*W +: W])
            );
        end
    endgenerate

    // Row 0 and column 0 are not delayed.
    assign a_row_in[0 +: W] = a_pick[0 +: W];     // wiring only
    assign b_col_in[0 +: W] = b_pick[0 +: W];     // wiring only

    // Rows / columns 1, 2, 3 are delayed by 1, 2, 3 clock cycles.
    genvar d;
    generate
        for (d = 1; d < 4; d = d + 1) begin : skew
            skew_chain #(.W(W), .STAGES(d)) u_skew_a (
                .clk   (clk),
                .clear (clear),
                .din   (a_pick[d*W +: W]),
                .dout  (a_row_in[d*W +: W])
            );
            skew_chain #(.W(W), .STAGES(d)) u_skew_b (
                .clk   (clk),
                .clear (clear),
                .din   (b_pick[d*W +: W]),
                .dout  (b_col_in[d*W +: W])
            );
        end
    endgenerate

endmodule
