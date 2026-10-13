// Top level: connects the controller to the systolic array.
module top (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [127:0] A_flat,
    input  wire [127:0] B_flat,
    output wire [319:0] C_flat,
    output wire         done
);

    wire [31:0] a_row_in;   // A values fed to the rows
    wire [31:0] b_col_in;   // B values fed to the columns
    wire        clear;      // clears the accumulators

    // Controller
    control u_control (
        .clk      (clk),
        .rst      (rst),
        .start    (start),
        .A_flat   (A_flat),
        .B_flat   (B_flat),
        .a_row_in (a_row_in),
        .b_col_in (b_col_in),
        .clear    (clear),
        .done     (done)
    );

    // PE grid
    systolic_array u_array (
        .clk      (clk),
        .rst      (rst),
        .clear    (clear),
        .a_row_in (a_row_in),
        .b_col_in (b_col_in),
        .c_flat   (C_flat)
    );

endmodule
