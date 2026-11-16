// W x W unsigned array multiplier (W = 4 by default, so 4 x 4 -> 8 bits).
// The name says 4x4 but W can be changed (for example 8) without editing the code.
//
// How it works (same as multiplying by hand):
//   1. Partial product j = a AND b[j]   (a row of W AND gates, W rows).
//   2. Row 0 is the first partial sum.
//   3. For j = 1 .. W-1: shift the previous sum right by one place (its lowest
//      bit is already a final product bit), then add partial product j with
//      a W-bit ripple adder. That adder is the "row j" of the array.
// Product bit j is the lowest bit of the sum of row j. The top W bits are the
// last carry and the upper bits of the last sum.
// Gates for W = 4: 16 AND (partial products) + 3 adders x 4 full adders x 5 = 76.
module mult_4x4 #(
    parameter W = 4
) (
    input  [W-1:0]   a,
    input  [W-1:0]   b,
    output [2*W-1:0] p
);

    wire [W*W-1:0] pp;      // partial products: row j is pp[j*W +: W]
    wire [W*W-1:0] row_sum; // sum of row j is row_sum[j*W +: W]
    wire [W-1:0]   row_cout;// carry-out of row j

    genvar j;
    genvar k;

    // 1. Partial products: pp[j][k] = a[k] AND b[j]
    generate
        for (j = 0; j < W; j = j + 1) begin : pp_row
            for (k = 0; k < W; k = k + 1) begin : pp_bit
                and g_pp (pp[j*W+k], a[k], b[j]);
            end
        end
    endgenerate

    // 2. Row 0: the first partial sum is just partial product 0, no carry.
    assign row_sum[0 +: W] = pp[0 +: W];    // wiring only
    assign row_cout[0]     = 1'b0;          // wiring only (constant)

    // 3. Rows 1 .. W-1: add partial product j to the shifted previous sum.
    generate
        for (j = 1; j < W; j = j + 1) begin : add_row
            adder_n #(.N(W)) u_add (
                .a    ({row_cout[j-1], row_sum[(j-1)*W+1 +: W-1]}),
                .b    (pp[j*W +: W]),
                .cin  (1'b0),
                .sum  (row_sum[j*W +: W]),
                .cout (row_cout[j])
            );
        end
    endgenerate

    // Product bits 0 .. W-1: the lowest bit of each row's sum.
    generate
        for (j = 0; j < W; j = j + 1) begin : low_bits
            assign p[j] = row_sum[j*W];     // wiring only
        end
    endgenerate

    // Product bits W .. 2W-1: last carry and the upper bits of the last sum.
    assign p[2*W-1:W] = {row_cout[W-1], row_sum[(W-1)*W+1 +: W-1]};    // wiring only

endmodule
