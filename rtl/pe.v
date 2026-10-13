// Processing element: multiplies a_in * b_in, adds to acc,
// and passes a_in right and b_in down (one register stage each).
module pe (
    input  wire        clk,
    input  wire        rst,
    input  wire        clear,
    input  wire [7:0]  a_in,
    input  wire [7:0]  b_in,
    output reg  [7:0]  a_out,
    output reg  [7:0]  b_out,
    output reg  [19:0] acc
);

    // 8x8 product, 16 bits wide
    wire [15:0] product;
    assign product = a_in * b_in;

    // Sequential block: reset, clear, or multiply-accumulate and pass-through
    always @(posedge clk) begin
        if (rst || clear) begin
            acc   <= 20'd0;
            a_out <= 8'd0;
            b_out <= 8'd0;
        end else begin
            acc   <= acc + product;
            a_out <= a_in;
            b_out <= b_in;
        end
    end

endmodule
