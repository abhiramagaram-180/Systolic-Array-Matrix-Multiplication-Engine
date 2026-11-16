// Top level (gate-level version): control + feeder + systolic array.
// Same ports as rtl/top.v, with widths set by W (input width) and ACC (accumulator width).
// Defaults: W = 4 (inputs 0..15), ACC = 10 (largest result 4*15*15 = 900 < 1024).
// For 8-bit inputs use W = 8, ACC = 20.
module top #(
    parameter W   = 4,
    parameter ACC = 10
) (
    input               clk,
    input               rst,
    input               start,
    input  [16*W-1:0]   A_flat,
    input  [16*W-1:0]   B_flat,
    output [16*ACC-1:0] C_flat,
    output              done
);

    wire [3:0]   t;             // cycle counter
    wire         clear;         // wipes the datapath
    wire [4*W-1:0] a_row_in;    // skewed A values, one per row
    wire [4*W-1:0] b_col_in;    // skewed B values, one per column

    control u_control (
        .clk   (clk),
        .rst   (rst),
        .start (start),
        .t     (t),
        .clear (clear),
        .done  (done)
    );

    feeder #(.W(W)) u_feeder (
        .clk      (clk),
        .clear    (clear),
        .t        (t),
        .A_flat   (A_flat),
        .B_flat   (B_flat),
        .a_row_in (a_row_in),
        .b_col_in (b_col_in)
    );

    systolic_array #(.W(W), .ACC(ACC)) u_array (
        .clk      (clk),
        .clear    (clear),
        .a_row_in (a_row_in),
        .b_col_in (b_col_in),
        .c_flat   (C_flat)
    );

endmodule
