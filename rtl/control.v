// Controller: FSM IDLE -> RUN -> DONE, plus the data feeder.
// Row i gets A[i][t-i], column j gets B[t-j][j]; zero when index is outside 0..3.
module control (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [127:0] A_flat,
    input  wire [127:0] B_flat,
    output reg  [31:0]  a_row_in,
    output reg  [31:0]  b_col_in,
    output wire         clear,
    output wire         done
);

    // State encoding
    localparam IDLE = 2'd0;
    localparam RUN  = 2'd1;
    localparam DONE = 2'd2;

    reg [1:0] state;    // current FSM state
    reg [3:0] t;        // cycle counter, 0..9 while running

    integer n;          // loop index for row/column feeding
    integer k;          // matrix index selected for row/column n

    // clear pulses for one cycle when start is accepted (not while running)
    assign clear = start && (state != RUN);

    // done is high while in the DONE state
    assign done = (state == DONE);

    // FSM: state and cycle counter
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            t     <= 4'd0;
        end else begin
            case (state)
                IDLE: begin
                    t <= 4'd0;
                    if (start) state <= RUN;
                end
                RUN: begin
                    t <= t + 4'd1;
                    if (t == 4'd9) state <= DONE;
                end
                DONE: begin
                    t <= 4'd0;
                    if (start) state <= RUN;
                end
                default: state <= IDLE;
            endcase
        end
    end

    // Feeder: pick the A and B values for the current cycle t
    always @(state or t or A_flat or B_flat) begin
        a_row_in = 32'd0;
        b_col_in = 32'd0;
        if (state == RUN) begin
            for (n = 0; n < 4; n = n + 1) begin
                // row n: A[n][t-n]
                k = t - n;
                if (k >= 0 && k <= 3)
                    a_row_in[n*8 +: 8] = A_flat[(n*4 + k)*8 +: 8];
                // column n: B[t-n][n]
                if (k >= 0 && k <= 3)
                    b_col_in[n*8 +: 8] = B_flat[(k*4 + n)*8 +: 8];
            end
        end
    end

endmodule
