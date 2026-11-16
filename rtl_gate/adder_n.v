// N-bit ripple-carry adder: N full adders in a row.
// The carry of bit i goes into bit i+1. carry[0] is the carry-in and
// carry[N] is the carry-out. ("assign" is used here only to give a
// signal a second name; there is no logic in it.)
module adder_n #(
    parameter N = 4
) (
    input  [N-1:0] a,
    input  [N-1:0] b,
    input          cin,
    output [N-1:0] sum,
    output         cout
);

    wire [N:0] carry;           // carry[i] enters bit i

    assign carry[0] = cin;      // wiring only
    assign cout     = carry[N]; // wiring only

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : bit_slice
            fa u_fa (
                .a    (a[i]),
                .b    (b[i]),
                .cin  (carry[i]),
                .sum  (sum[i]),
                .cout (carry[i+1])
            );
        end
    endgenerate

endmodule
