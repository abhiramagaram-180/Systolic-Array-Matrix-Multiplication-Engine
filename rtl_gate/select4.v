// 4-to-1 selector built from AND and OR gates (replaces one ROM).
// din holds four W-bit values: value k is din[k*W +: W].
// sel is "one-hot": at most one select line is 1.
//   y = (sel[0] AND value0) OR (sel[1] AND value1) OR (sel[2] AND value2) OR (sel[3] AND value3)
// If no select line is 1, y = 0.
// Per bit: 4 AND, then 3 OR (two pairs, then one OR of the pairs) = 7 two-input gates.
module select4 #(
    parameter W = 4
) (
    input  [3:0]     sel,
    input  [4*W-1:0] din,
    output [W-1:0]   y
);

    wire [4*W-1:0] picked;      // each value ANDed with its select line
    wire [W-1:0]   or_01;       // value 0 or value 1
    wire [W-1:0]   or_23;       // value 2 or value 3

    genvar b;
    genvar k;
    generate
        for (b = 0; b < W; b = b + 1) begin : bit_slice
            for (k = 0; k < 4; k = k + 1) begin : pick
                and g_and (picked[k*W+b], sel[k], din[k*W+b]);
            end
            or g_or01 (or_01[b], picked[0*W+b], picked[1*W+b]);
            or g_or23 (or_23[b], picked[2*W+b], picked[3*W+b]);
            or g_or   (y[b],     or_01[b],      or_23[b]);
        end
    endgenerate

endmodule
