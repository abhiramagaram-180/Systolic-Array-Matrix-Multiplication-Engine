// Full adder: adds three 1-bit numbers (a, b and the carry-in cin).
//   sum  = a XOR b XOR cin
//   cout = (a AND b) OR ((a XOR b) AND cin)
// Built only from gate primitives: 2 XOR + 2 AND + 1 OR = 5 gates.
module fa (
    input  a,
    input  b,
    input  cin,
    output sum,
    output cout
);

    wire a_xor_b;       // a XOR b (used twice)
    wire a_and_b;       // carry made by a and b alone
    wire xor_and_cin;   // carry made by the carry-in

    xor g_xor1 (a_xor_b, a, b);
    xor g_xor2 (sum, a_xor_b, cin);
    and g_and1 (a_and_b, a, b);
    and g_and2 (xor_and_cin, a_xor_b, cin);
    or  g_or1  (cout, a_and_b, xor_and_cin);

endmodule
