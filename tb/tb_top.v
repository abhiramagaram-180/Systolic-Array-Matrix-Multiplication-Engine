// Testbench for the 4x4 systolic matrix multiplier.
`timescale 1ns/1ps
module tb_top;

    reg          clk;
    reg          rst;
    reg          start;
    reg  [127:0] A_flat;
    reg  [127:0] B_flat;
    wire [319:0] C_flat;
    wire         done;

    integer i;
    integer j;
    integer k;
    integer errors;         // mismatches in the current test
    integer wait_cycles;    // timeout counter
    integer expected;       // expected value of one C element
    integer actual;         // value read from the design

    // Device under test
    top dut (
        .clk    (clk),
        .rst    (rst),
        .start  (start),
        .A_flat (A_flat),
        .B_flat (B_flat),
        .C_flat (C_flat),
        .done   (done)
    );

    // 10 ns clock
    initial clk = 0;
    always #5 clk = ~clk;

    // Waveform dump
    initial begin
        $dumpfile("dump.vcd");
        $dumpvars(0, tb_top);
    end

    // Run one multiplication with the current A_flat/B_flat and check it
    task run_test;
        input [8*20:1] name;
        begin
            // Pulse start for one clock cycle
            @(posedge clk);
            #1 start = 1;
            @(posedge clk);
            #1 start = 0;

            // Wait for done (with a timeout)
            wait_cycles = 0;
            while (done == 0 && wait_cycles < 100) begin
                @(posedge clk);
                #1 wait_cycles = wait_cycles + 1;
            end

            // Compare every C element against a software reference
            errors = 0;
            if (done == 0) errors = errors + 1;
            for (i = 0; i < 4; i = i + 1) begin
                for (j = 0; j < 4; j = j + 1) begin
                    expected = 0;
                    for (k = 0; k < 4; k = k + 1)
                        expected = expected + A_flat[(i*4+k)*8 +: 8] * B_flat[(k*4+j)*8 +: 8];
                    actual = C_flat[(i*4+j)*20 +: 20];
                    if (actual !== expected) begin
                        errors = errors + 1;
                        $display("  mismatch C[%0d][%0d]: got %0d, expected %0d", i, j, actual, expected);
                    end
                end
            end

            if (errors == 0) $display("PASS: %0s", name);
            else             $display("FAIL: %0s", name);
        end
    endtask

    // Main stimulus
    initial begin
        rst   = 1;
        start = 0;
        A_flat = 128'd0;
        B_flat = 128'd0;
        repeat (3) @(posedge clk);
        #1 rst = 0;

        // Test 1: A = identity, B = 1..16 (result must equal B)
        A_flat = 128'd0;
        A_flat[0*8 +: 8]  = 8'd1;
        A_flat[5*8 +: 8]  = 8'd1;
        A_flat[10*8 +: 8] = 8'd1;
        A_flat[15*8 +: 8] = 8'd1;
        B_flat = {8'd16, 8'd15, 8'd14, 8'd13, 8'd12, 8'd11, 8'd10, 8'd9,
                  8'd8,  8'd7,  8'd6,  8'd5,  8'd4,  8'd3,  8'd2,  8'd1};
        run_test("identity");

        // Test 2: all zeros
        A_flat = 128'd0;
        B_flat = 128'd0;
        run_test("all zeros");

        // Test 3: all ones (every C element must be 4)
        A_flat = {16{8'd1}};
        B_flat = {16{8'd1}};
        run_test("all ones");

        // Test 4: all 255 (every C element must be 260100)
        A_flat = {16{8'd255}};
        B_flat = {16{8'd255}};
        run_test("all 255");

        // Test 5: hand-picked case, A = 1..16, B = reversed 16..1
        A_flat = {8'd16, 8'd15, 8'd14, 8'd13, 8'd12, 8'd11, 8'd10, 8'd9,
                  8'd8,  8'd7,  8'd6,  8'd5,  8'd4,  8'd3,  8'd2,  8'd1};
        B_flat = {8'd1,  8'd2,  8'd3,  8'd4,  8'd5,  8'd6,  8'd7,  8'd8,
                  8'd9,  8'd10, 8'd11, 8'd12, 8'd13, 8'd14, 8'd15, 8'd16};
        run_test("hand-picked");

        $finish;
    end

endmodule
