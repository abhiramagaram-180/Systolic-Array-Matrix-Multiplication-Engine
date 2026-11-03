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
    integer seed;           // fixed seed so random runs are repeatable
    integer run;            // loop counter for the random group
    integer idx;            // byte index when filling random matrices
    integer group_errors;   // mismatches over a whole group of runs
    integer total_groups;   // number of test groups run so far
    integer passed_groups;  // number of test groups that passed

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

    // Run one multiplication with the current A_flat/B_flat and check it.
    // Leaves the number of mismatches in 'errors'. Prints nothing but mismatches.
    task run_and_check;
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

        end
    endtask

    // Run one test, print PASS or FAIL for it and update the totals
    task run_test;
        input [8*20:1] name;
        begin
            run_and_check;
            total_groups = total_groups + 1;
            if (errors == 0) begin
                passed_groups = passed_groups + 1;
                $display("PASS: %0s", name);
            end else
                $display("FAIL: %0s", name);
        end
    endtask

    // Main stimulus
    initial begin
        seed          = 12345;
        total_groups  = 0;
        passed_groups = 0;
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

        // Test 6: B = identity, A = 1..16 (result must equal A)
        A_flat = {8'd16, 8'd15, 8'd14, 8'd13, 8'd12, 8'd11, 8'd10, 8'd9,
                  8'd8,  8'd7,  8'd6,  8'd5,  8'd4,  8'd3,  8'd2,  8'd1};
        B_flat = 128'd0;
        B_flat[0*8 +: 8]  = 8'd1;
        B_flat[5*8 +: 8]  = 8'd1;
        B_flat[10*8 +: 8] = 8'd1;
        B_flat[15*8 +: 8] = 8'd1;
        run_test("B identity");

        // Test 7: single hot cell, A[2][1] = 200 and B[1][3] = 150,
        // so only C[2][3] = 30000 is nonzero
        A_flat = 128'd0;
        B_flat = 128'd0;
        A_flat[(2*4+1)*8 +: 8] = 8'd200;
        B_flat[(1*4+3)*8 +: 8] = 8'd150;
        run_test("single hot cell");

        // Test 8: 50 runs with random bytes, one PASS/FAIL line for the group
        group_errors = 0;
        for (run = 0; run < 50; run = run + 1) begin
            for (idx = 0; idx < 16; idx = idx + 1) begin
                A_flat[idx*8 +: 8] = $random(seed) & 255;
                B_flat[idx*8 +: 8] = $random(seed) & 255;
            end
            run_and_check;
            if (errors != 0) $display("  random run %0d failed", run);
            group_errors = group_errors + errors;
        end
        errors = group_errors;
        total_groups = total_groups + 1;
        if (group_errors == 0) begin
            passed_groups = passed_groups + 1;
            $display("PASS: random x 50");
        end else
            $display("FAIL: random x 50");

        $display("TOTAL: %0d of %0d test groups passed", passed_groups, total_groups);
        $finish;
    end

endmodule
