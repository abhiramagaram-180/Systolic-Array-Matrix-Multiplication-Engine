// 4x4 grid of PEs. A flows right along rows, B flows down along columns.
module systolic_array (
    input  wire         clk,
    input  wire         rst,
    input  wire         clear,
    input  wire [31:0]  a_row_in,   // one 8-bit A value per row
    input  wire [31:0]  b_col_in,   // one 8-bit B value per column
    output wire [319:0] c_flat      // 16 accumulators, 20 bits each
);

    // a_link: 4 rows x 5 columns of 8-bit wires; entry (i*5+j) feeds PE(i,j)
    wire [159:0] a_link;
    // b_link: 5 rows x 4 columns of 8-bit wires; entry (i*4+j) feeds PE(i,j)
    wire [159:0] b_link;

    genvar i;
    genvar j;

    // Connect the row inputs to the left edge of the array
    generate
        for (i = 0; i < 4; i = i + 1) begin : row_inputs
            assign a_link[(i*5)*8 +: 8] = a_row_in[i*8 +: 8];
        end
    endgenerate

    // Connect the column inputs to the top edge of the array
    generate
        for (j = 0; j < 4; j = j + 1) begin : col_inputs
            assign b_link[j*8 +: 8] = b_col_in[j*8 +: 8];
        end
    endgenerate

    // Create the 16 processing elements
    generate
        for (i = 0; i < 4; i = i + 1) begin : pe_row
            for (j = 0; j < 4; j = j + 1) begin : pe_col
                pe u_pe (
                    .clk   (clk),
                    .rst   (rst),
                    .clear (clear),
                    .a_in  (a_link[(i*5+j)*8 +: 8]),
                    .b_in  (b_link[(i*4+j)*8 +: 8]),
                    .a_out (a_link[(i*5+j+1)*8 +: 8]),
                    .b_out (b_link[((i+1)*4+j)*8 +: 8]),
                    .acc   (c_flat[(i*4+j)*20 +: 20])
                );
            end
        end
    endgenerate

endmodule
