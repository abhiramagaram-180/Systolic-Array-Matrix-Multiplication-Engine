// Testbench for the gate-level systolic array (rtl_gate/).
// Unit tests: fa (all 8 inputs), adder_n (all inputs), mult_4x4 (all input pairs).
// System tests: matrices are checked against a software triple loop.
// Values are W bits wide (W = 4 gives 0..15). To try 8-bit inputs with 20-bit
// accumulators compile with -DW8 (or: bash scripts/run_gate.sh w8).
`timescale 1ns/1ps
module tb_top;

`ifdef W8
    parameter W   = 8;      // input width
    parameter ACC = 20;     // accumulator width
`else
    parameter W   = 4;      // input width
    parameter ACC = 10;     // accumulator width (4*15*15 = 900 < 1024)
`endif

    reg                 clk;
    reg                 rst;
    reg                 start;
    reg  [16*W-1:0]     A_flat;
    reg  [16*W-1:0]     B_flat;
    wire [16*ACC-1:0]   C_flat;
    wire                done;

    integer maxv;           // largest input value, 2^W - 1
    integer i;
    integer j;
    integer k;
    integer n;
    integer errors;         // mismatches in the current test
    integer wait_cycles;    // cycles from the start edge until done
    integer expected;
    integer actual;
    integer seed;
    integer run;
    integer idx;
    integer group_errors;
    integer total_groups;
    integer passed_groups;

    // ---------------------------------------------------------------- DUT
    top #(.W(W), .ACC(ACC)) dut (
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

    // ------------------------------------------------ unit test: full adder
    reg  fa_a, fa_b, fa_cin;
    wire fa_sum, fa_cout;
    fa u_fa_test (.a(fa_a), .b(fa_b), .cin(fa_cin), .sum(fa_sum), .cout(fa_cout));

    // ----------------------------------------------- unit test: adder_n (W bits)
    reg  [W-1:0] ad_a, ad_b;
    reg          ad_cin;
    wire [W-1:0] ad_sum;
    wire         ad_cout;
    adder_n #(.N(W)) u_adder_test (.a(ad_a), .b(ad_b), .cin(ad_cin), .sum(ad_sum), .cout(ad_cout));

    // ------------------------------------------- unit test: multiplier
    reg  [W-1:0]   mu_a, mu_b;
    wire [2*W-1:0] mu_p;
    mult_4x4 #(.W(W)) u_mult_test (.a(mu_a), .b(mu_b), .p(mu_p));

    integer ad_expected;
    integer a_val;
    integer b_val;

    task report;
        input [8*32:1] name;
        input integer  errs;
        begin
            total_groups = total_groups + 1;
            if (errs == 0) begin
                passed_groups = passed_groups + 1;
                $display("PASS: %0s", name);
            end else
                $display("FAIL: %0s (%0d errors)", name, errs);
        end
    endtask

    task test_fa;
        begin
            errors = 0;
            for (n = 0; n < 8; n = n + 1) begin
                fa_a = n[2]; fa_b = n[1]; fa_cin = n[0];
                #1;
                expected = fa_a + fa_b + fa_cin;
                actual   = fa_sum + 2 * fa_cout;
                if (actual !== expected) begin
                    errors = errors + 1;
                    $display("  fa a=%b b=%b cin=%b: sum=%b cout=%b", fa_a, fa_b, fa_cin, fa_sum, fa_cout);
                end
            end
            report("fa all 8 inputs", errors);
        end
    endtask

    task test_adder;
        begin
            errors = 0;
            for (a_val = 0; a_val <= maxv; a_val = a_val + 1)
                for (b_val = 0; b_val <= maxv; b_val = b_val + 1)
                    for (n = 0; n < 2; n = n + 1) begin
                        ad_a = a_val; ad_b = b_val; ad_cin = n;
                        #1;
                        ad_expected = a_val + b_val + n;
                        actual = ad_sum + (ad_cout << W);
                        if (actual !== ad_expected) errors = errors + 1;
                    end
            report("adder_n all inputs", errors);
        end
    endtask

    task test_mult;
        begin
            errors = 0;
            for (a_val = 0; a_val <= maxv; a_val = a_val + 1)
                for (b_val = 0; b_val <= maxv; b_val = b_val + 1) begin
                    mu_a = a_val; mu_b = b_val;
                    #1;
                    if (mu_p !== a_val * b_val) begin
                        errors = errors + 1;
                        if (errors < 5) $display("  mult %0d * %0d = %0d", a_val, b_val, mu_p);
                    end
                end
            report("mult_4x4 all pairs", errors);
        end
    endtask

    // ------------------------------------------------ system test helpers
    // Put one value into A[i][k] / B[k][j]
    task put_a;
        input integer ai;
        input integer ak;
        input integer v;
        begin
            A_flat[(ai*4+ak)*W +: W] = v;
        end
    endtask

    task put_b;
        input integer bk;
        input integer bj;
        input integer v;
        begin
            B_flat[(bk*4+bj)*W +: W] = v;
        end
    endtask

    // One multiplication: pulse start, wait for done, check latency and all C values.
    // Leaves the number of mismatches in 'errors'.
    task run_and_check;
        begin
            // one clock after done, so that run has fallen (a new start is accepted)
            @(posedge clk);
            #1 start = 1;
            @(posedge clk);          // start edge: clear applied, run = 1, t = 0
            #1 start = 0;
            wait_cycles = 0;
            while (done == 0 && wait_cycles < 100) begin
                @(posedge clk);
                #1 wait_cycles = wait_cycles + 1;
            end
            errors = 0;
            if (wait_cycles != 10) begin
                errors = errors + 1;
                $display("  latency %0d cycles, expected 10", wait_cycles);
            end
            for (i = 0; i < 4; i = i + 1) begin
                for (j = 0; j < 4; j = j + 1) begin
                    expected = 0;
                    for (k = 0; k < 4; k = k + 1)
                        expected = expected + A_flat[(i*4+k)*W +: W] * B_flat[(k*4+j)*W +: W];
                    actual = C_flat[(i*4+j)*ACC +: ACC];
                    if (actual !== expected) begin
                        errors = errors + 1;
                        $display("  mismatch C[%0d][%0d]: got %0d, expected %0d", i, j, actual, expected);
                    end
                end
            end
        end
    endtask

    task run_test;
        input [8*32:1] name;
        begin
            run_and_check;
            report(name, errors);
        end
    endtask

    // ------------------------------------------------------------- main
    initial begin
        maxv          = (1 << W) - 1;
        seed          = 12345;
        total_groups  = 0;
        passed_groups = 0;
        rst    = 1;
        start  = 0;
        A_flat = 0;
        B_flat = 0;

        // unit tests first (no clock needed)
        test_fa;
        test_adder;
        test_mult;

        // reset the controller for two clock edges
        repeat (2) @(posedge clk);
        #1 rst = 0;

        // 1. all zeros
        A_flat = 0;
        B_flat = 0;
        run_test("zeros");

        // 2. all ones (every C is 4)
        for (idx = 0; idx < 16; idx = idx + 1) begin
            A_flat[idx*W +: W] = 1;
            B_flat[idx*W +: W] = 1;
        end
        run_test("ones");

        // 3. A = identity, B = 1,2,3,... (not symmetric): C must equal B
        A_flat = 0;
        put_a(0, 0, 1);
        put_a(1, 1, 1);
        put_a(2, 2, 1);
        put_a(3, 3, 1);
        for (idx = 0; idx < 16; idx = idx + 1)
            B_flat[idx*W +: W] = (idx + 1) & maxv;
        run_test("identity (B not symmetric)");

        // 4. all values at the maximum (every C is 4*15*15 = 900 for W = 4)
        for (idx = 0; idx < 16; idx = idx + 1) begin
            A_flat[idx*W +: W] = maxv;
            B_flat[idx*W +: W] = maxv;
        end
        run_test("all_15 (all max)");

        // 5. hand-picked, not symmetric: A = 1,2,3,... and B = 15,14,13,...
        for (idx = 0; idx < 16; idx = idx + 1) begin
            A_flat[idx*W +: W] = (idx + 1) & maxv;
            B_flat[idx*W +: W] = maxv - idx;
        end
        run_test("hand_picked");

        // 6. single non-zero cell: A[2][1] and B[1][3] only, so only C[2][3] is non-zero
        A_flat = 0;
        B_flat = 0;
        put_a(2, 1, maxv - 2);
        put_b(1, 3, maxv);
        run_test("single hot cell");

        // 7. 50 random matrix pairs, one line for the whole group
        group_errors = 0;
        for (run = 0; run < 50; run = run + 1) begin
            for (idx = 0; idx < 16; idx = idx + 1) begin
                A_flat[idx*W +: W] = $random(seed) & maxv;
                B_flat[idx*W +: W] = $random(seed) & maxv;
            end
            run_and_check;
            if (errors != 0) $display("  random run %0d failed", run);
            group_errors = group_errors + errors;
        end
        report("random x 50", group_errors);

        // 8. two back-to-back runs without reset, with different data
        group_errors = 0;
        for (idx = 0; idx < 16; idx = idx + 1) begin
            A_flat[idx*W +: W] = (idx + 3) & maxv;
            B_flat[idx*W +: W] = (idx * 5 + 1) & maxv;
        end
        run_and_check;
        group_errors = group_errors + errors;
        for (idx = 0; idx < 16; idx = idx + 1) begin
            A_flat[idx*W +: W] = maxv - ((idx * 3) & maxv);
            B_flat[idx*W +: W] = (idx * 7 + 2) & maxv;
        end
        run_and_check;
        group_errors = group_errors + errors;
        report("back-to-back x 2", group_errors);

        $display("TOTAL: %0d of %0d test groups passed", passed_groups, total_groups);
        $finish;
    end

endmodule
