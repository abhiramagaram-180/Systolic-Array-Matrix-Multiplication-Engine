// Processing element (one cell of the array).
// Every clock: acc <= acc + a_in * b_in, a_out <= a_in, b_out <= b_in.
//   mult_4x4 : multiplies a_in and b_in (2W-bit product)
//   adder_n  : adds the product (padded with zeros to ACC bits) to acc
//   reg_n    : acc register, plus one W-bit register each for a_out and b_out
// clear = 1 sets acc, a_out and b_out to 0 on the next clock edge.
module pe #(
    parameter W   = 4,      // input width
    parameter ACC = 10      // accumulator width (must be bigger than 2*W)
) (
    input            clk,
    input            clear,
    input  [W-1:0]   a_in,
    input  [W-1:0]   b_in,
    output [W-1:0]   a_out,
    output [W-1:0]   b_out,
    output [ACC-1:0] acc
);

    wire [2*W-1:0] product;     // a_in * b_in
    wire [ACC-1:0] sum;         // acc + product

    mult_4x4 #(.W(W)) u_mult (
        .a (a_in),
        .b (b_in),
        .p (product)
    );

    // zero-extend the product with constant 0 bits, then add it to acc
    adder_n #(.N(ACC)) u_add (
        .a    (acc),
        .b    ({{(ACC-2*W){1'b0}}, product}),
        .cin  (1'b0),
        .sum  (sum),
        .cout ()
    );

    reg_n #(.N(ACC)) u_acc   (.clk(clk), .clear(clear), .d(sum),  .q(acc));
    reg_n #(.N(W))   u_a_reg (.clk(clk), .clear(clear), .d(a_in), .q(a_out));
    reg_n #(.N(W))   u_b_reg (.clk(clk), .clear(clear), .d(b_in), .q(b_out));

endmodule
