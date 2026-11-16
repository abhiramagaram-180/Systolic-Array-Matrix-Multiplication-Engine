// 4x4 grid of PEs. A flows right along rows, B flows down along columns.
// a_link: 4 rows x 5 columns of W-bit wires; entry (i*5+j) is the A input of PE(i,j)
//         and entry (i*5+j+1) is its A output (= the A input of PE(i,j+1)).
// b_link: 5 rows x 4 columns of W-bit wires; entry (i*4+j) is the B input of PE(i,j)
//         and entry ((i+1)*4+j) is its B output (= the B input of PE(i+1,j)).
// c_flat holds the 16 accumulators: C[i][j] = c_flat[(i*4+j)*ACC +: ACC].
module systolic_array #(
    parameter W   = 4,
    parameter ACC = 10
) (
    input                clk,
    input                clear,
    input  [4*W-1:0]     a_row_in,   // one W-bit A value per row
    input  [4*W-1:0]     b_col_in,   // one W-bit B value per column
    output [16*ACC-1:0]  c_flat
);

    wire [20*W-1:0] a_link;
    wire [20*W-1:0] b_link;

    genvar i;
    genvar j;

    // left edge: row inputs enter PE(i,0)
    generate
        for (i = 0; i < 4; i = i + 1) begin : row_inputs
            assign a_link[(i*5)*W +: W] = a_row_in[i*W +: W];     // wiring only
        end
    endgenerate

    // top edge: column inputs enter PE(0,j)
    generate
        for (j = 0; j < 4; j = j + 1) begin : col_inputs
            assign b_link[j*W +: W] = b_col_in[j*W +: W];         // wiring only
        end
    endgenerate

    // the 16 processing elements
    generate
        for (i = 0; i < 4; i = i + 1) begin : pe_row
            for (j = 0; j < 4; j = j + 1) begin : pe_col
                pe #(.W(W), .ACC(ACC)) u_pe (
                    .clk   (clk),
                    .clear (clear),
                    .a_in  (a_link[(i*5+j)*W +: W]),
                    .b_in  (b_link[(i*4+j)*W +: W]),
                    .a_out (a_link[(i*5+j+1)*W +: W]),
                    .b_out (b_link[((i+1)*4+j)*W +: W]),
                    .acc   (c_flat[(i*4+j)*ACC +: ACC])
                );
            end
        end
    endgenerate

endmodule
