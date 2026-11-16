"""Test cases for the gate-level design (W-bit unsigned inputs, 4x4 matrices).

Run from the project root:
    python logisim/make_cases_gate.py          (W = 4, inputs 0..15)
    python logisim/make_cases_gate.py 8        (W = 8, inputs 0..255)

It prints A, B and the expected C = A x B for every case. C is computed with a
plain triple loop and asserted against a second method (rows times columns with
zip). The same cases are used by the Verilog testbench (tb_gate/tb_top.v) and
by the Logisim wrapper circuits (logisim/systolic_gate_level.circ).
Python 3 standard library only.
"""
import random
import sys

N = 4                       # matrix size
SEED = 12345                # fixed seed for the random case


def case_names():
    return ["zeros", "ones", "identity", "all_max", "hand_picked", "single_hot", "random"]


def make_case(name, w):
    """Return (A, B) as 4x4 lists of lists for case 'name' and input width w."""
    maxv = (1 << w) - 1
    a = [[0] * N for _ in range(N)]
    b = [[0] * N for _ in range(N)]
    if name == "zeros":
        pass
    elif name == "ones":
        a = [[1] * N for _ in range(N)]
        b = [[1] * N for _ in range(N)]
    elif name == "identity":                    # A = identity, B = 1,2,3,... (not symmetric)
        for i in range(N):
            a[i][i] = 1
        for i in range(N):
            for j in range(N):
                b[i][j] = (i * N + j + 1) & maxv
    elif name == "all_max":                     # every value is the largest input
        a = [[maxv] * N for _ in range(N)]
        b = [[maxv] * N for _ in range(N)]
    elif name == "hand_picked":                 # A = 1,2,3,...  B = max, max-1, ... (not symmetric)
        for i in range(N):
            for j in range(N):
                a[i][j] = (i * N + j + 1) & maxv
                b[i][j] = maxv - (i * N + j)
    elif name == "single_hot":                  # only C[2][3] is non-zero
        a[2][1] = maxv - 2
        b[1][3] = maxv
    elif name == "random":
        rng = random.Random(SEED)
        for i in range(N):
            for j in range(N):
                a[i][j] = rng.randint(0, maxv)
        for i in range(N):
            for j in range(N):
                b[i][j] = rng.randint(0, maxv)
    else:
        raise ValueError("unknown case " + name)
    return a, b


def multiply(a, b):
    """C = A x B, plain triple loop."""
    c = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            total = 0
            for k in range(N):
                total = total + a[i][k] * b[k][j]
            c[i][j] = total
    return c


def multiply_second_method(a, b):
    """Same result with a different method: row of A zipped with column of B."""
    cols = [[b[k][j] for k in range(N)] for j in range(N)]
    return [[sum(x * y for x, y in zip(a[i], cols[j])) for j in range(N)] for i in range(N)]


def expected(a, b, acc_bits):
    c = multiply(a, b)
    assert c == multiply_second_method(a, b), "two methods disagree"
    assert all(v < (1 << acc_bits) for row in c for v in row), "result does not fit in the accumulator"
    return c


def rows_packed(a, w):
    """A_row[i] as one number: A[i][k] at bits [k*w +: w] (same packing as the Verilog A_flat)."""
    return [sum(a[i][k] << (k * w) for k in range(N)) for i in range(N)]


def cols_packed(b, w):
    """B_col[j] as one number: B[k][j] at bits [k*w +: w]."""
    return [sum(b[k][j] << (k * w) for k in range(N)) for j in range(N)]


def acc_width(w):
    """Accumulator width used by the project: 10 bits for W=4, 20 bits for W=8."""
    return {4: 10, 8: 20}.get(w, 2 * w + 2)


def fmt(m):
    return "[" + ", ".join("[" + ", ".join(str(v) for v in row) + "]" for row in m) + "]"


def main():
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    acc = acc_width(w)
    print("W = %d (inputs 0..%d), accumulator = %d bits" % (w, (1 << w) - 1, acc))
    for name in case_names():
        a, b = make_case(name, w)
        c = expected(a, b, acc)
        print("=" * 70)
        print("case %s" % name)
        print("  A =", fmt(a))
        print("  B =", fmt(b))
        print("  expected C (decimal):")
        for row in c:
            print("     " + " ".join("%7d" % v for v in row))
        print("  expected C (hex):")
        for row in c:
            print("     " + " ".join("%7X" % v for v in row))
        print("  A_row (hex, element k in bits [k*W +: W]):",
              " ".join("0x%0*X" % (w, v) for v in rows_packed(a, w)))
        print("  B_col (hex):                              ",
              " ".join("0x%0*X" % (w, v) for v in cols_packed(b, w)))


if __name__ == "__main__":
    main()
