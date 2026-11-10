"""Make Logisim ROM image files for the systolic array.

Usage (run from the project root):
    python logisim/make_rom.py 4 hand_picked      one case, N = 4
    python logisim/make_rom.py 2 paper_2x2        one case, N = 2
    python logisim/make_rom.py all                every case, and rewrite
                                                  logisim/test_cases.md

Cases: paper_2x2 (N=2 only), identity, b_identity, all_ones, all_255,
       hand_picked, random

For each case it writes 2N files into logisim/roms/<case>/ :
    A_row0.hex ... A_row{N-1}.hex   (row i holds A[i][t] at address t)
    B_col0.hex ... B_col{N-1}.hex   (column j holds B[t][j] at address t)
The data is UNSKEWED. The delay registers in the circuit do the skew.
For N = 2 the folder is called <case>_2x2 (except paper_2x2) so that the
N = 2 and N = 4 files do not overwrite each other.

Only the Python standard library is used.
"""

import os
import random
import sys

ROM_WORDS = 16          # the ROM has a 4-bit address, so 16 words
RANDOM_SEED = 12345     # fixed seed so the random case is repeatable
CASE_NAMES = ["paper_2x2", "identity", "b_identity", "all_ones",
              "all_255", "hand_picked", "random"]

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- matrices
def make_matrices(n, case):
    """Return (A, B) as lists of lists for the given case name."""
    count = n * n
    a = [[0] * n for _ in range(n)]
    b = [[0] * n for _ in range(n)]

    if case == "paper_2x2":
        if n != 2:
            raise ValueError("paper_2x2 only exists for N = 2")
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]
    elif case == "identity":                    # A = I, B = 1..N*N
        for i in range(n):
            a[i][i] = 1
        for i in range(n):
            for j in range(n):
                b[i][j] = i * n + j + 1
    elif case == "b_identity":                  # A = 1..N*N, B = I
        for i in range(n):
            for j in range(n):
                a[i][j] = i * n + j + 1
        for i in range(n):
            b[i][i] = 1
    elif case == "all_ones":
        a = [[1] * n for _ in range(n)]
        b = [[1] * n for _ in range(n)]
    elif case == "all_255":
        a = [[255] * n for _ in range(n)]
        b = [[255] * n for _ in range(n)]
    elif case == "hand_picked":                 # A = 1..N*N, B = N*N..1
        for i in range(n):
            for j in range(n):
                a[i][j] = i * n + j + 1
                b[i][j] = count - (i * n + j)
    elif case == "random":
        rng = random.Random(RANDOM_SEED)
        for i in range(n):
            for j in range(n):
                a[i][j] = rng.randint(0, 255)
        for i in range(n):
            for j in range(n):
                b[i][j] = rng.randint(0, 255)
    else:
        raise ValueError("unknown case: " + case)
    return a, b


# ------------------------------------------------------------ expected C
def multiply(n, a, b):
    """C = A x B with a plain triple loop."""
    c = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            total = 0
            for k in range(n):
                total = total + a[i][k] * b[k][j]
            c[i][j] = total
    return c


def multiply_second_method(n, a, b):
    """Same result by a different method (rows of A times columns of B)."""
    columns_of_b = [[b[k][j] for k in range(n)] for j in range(n)]
    return [[sum(x * y for x, y in zip(a[i], columns_of_b[j]))
             for j in range(n)] for i in range(n)]


def expected_c(n, a, b):
    """Compute C two ways, check they agree and fit in 20 bits."""
    c = multiply(n, a, b)
    assert c == multiply_second_method(n, a, b), "two methods disagree"
    for row in c:
        for value in row:
            assert value < 2 ** 20, "result does not fit in 20 bits"
    return c


# ------------------------------------------------------------ ROM files
def folder_name(n, case):
    if n == 2 and case != "paper_2x2":
        return case + "_2x2"
    return case


def write_hex_file(path, words):
    """Write one Logisim 'v2.0 raw' image: header line + 16 hex values."""
    assert len(words) == ROM_WORDS
    with open(path, "w") as f:
        f.write("v2.0 raw\n")
        f.write(" ".join("%x" % w for w in words) + "\n")


def write_roms(n, case, a, b):
    """Write the 2N ROM files. Returns the folder they went into."""
    folder = os.path.join(HERE, "roms", folder_name(n, case))
    os.makedirs(folder, exist_ok=True)
    for i in range(n):
        # row i: A[i][t] at address t for t < N, zeros after
        words = [a[i][t] if t < n else 0 for t in range(ROM_WORDS)]
        write_hex_file(os.path.join(folder, "A_row%d.hex" % i), words)
    for j in range(n):
        # column j: B[t][j] at address t for t < N, zeros after
        words = [b[t][j] if t < n else 0 for t in range(ROM_WORDS)]
        write_hex_file(os.path.join(folder, "B_col%d.hex" % j), words)
    return folder


# ------------------------------------------------------------- printing
def matrix_text(m):
    return "[" + ", ".join("[" + ", ".join(str(v) for v in row) + "]"
                           for row in m) + "]"


def print_case(n, case, a, b, c, folder):
    print("=" * 60)
    print("case %s   N = %d   files in %s" % (case, n, folder))
    print("A =", matrix_text(a))
    print("B =", matrix_text(b))
    print("expected C (decimal):")
    for row in c:
        print("   " + " ".join("%7d" % v for v in row))
    print("expected C (hex, 20 bit):")
    for row in c:
        print("   " + " ".join("%7s" % ("%05X" % v) for v in row))
    print("done goes high when t = 3N-2 = %d" % (3 * n - 2))
    print("after skew, value entering each row / column at each t")
    print("(row i gets A[i][t-i], column j gets B[t-j][j], else 0):")
    header = " t |" + "".join(" row%d" % i for i in range(n)) + " |" + \
             "".join(" col%d" % j for j in range(n))
    print(header)
    for t in range(10):
        row_vals = []
        for i in range(n):
            k = t - i
            row_vals.append(a[i][k] if 0 <= k < n else 0)
        col_vals = []
        for j in range(n):
            k = t - j
            col_vals.append(b[k][j] if 0 <= k < n else 0)
        print("%2d |" % t + "".join(" %4d" % v for v in row_vals) + " |" +
              "".join(" %4d" % v for v in col_vals))


def run_case(n, case):
    """Make files for one case and print everything. Returns the data."""
    a, b = make_matrices(n, case)
    c = expected_c(n, a, b)
    folder = write_roms(n, case, a, b)
    print_case(n, case, a, b, c, os.path.relpath(folder))
    return a, b, c


# ------------------------------------------------------- test_cases.md
def write_test_cases(results):
    """results: list of (n, case, a, b, c)."""
    lines = []
    lines.append("# Logisim test cases")
    lines.append("")
    lines.append("Generated by `python logisim/make_rom.py all`. "
                 "Do not edit by hand.")
    lines.append("")
    lines.append("ROM folder: `logisim/roms/<folder>/`. For N = 2 the folder "
                 "name ends in `_2x2`. Run length: 3N-2 ticks "
                 "(4 for N = 2, 10 for N = 4). Fill in the last column "
                 "after you run each case in Logisim.")
    lines.append("")
    lines.append("| N | Case | Folder | A | B | Expected C (decimal) | "
                 "Expected C (hex) | Logisim OK? |")
    lines.append("|---|------|--------|---|---|----------------------|"
                 "------------------|-------------|")
    for n, case, a, b, c in results:
        dec = matrix_text(c)
        hexa = "[" + ", ".join("[" + ", ".join("%05X" % v for v in row) + "]"
                               for row in c) + "]"
        lines.append("| %d | %s | `%s` | %s | %s | %s | %s |  |" % (
            n, case, folder_name(n, case), matrix_text(a), matrix_text(b),
            dec, hexa))
    lines.append("")
    path = os.path.join(HERE, "test_cases.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print("wrote", os.path.relpath(path))


# ----------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    if args == ["all"]:
        results = []
        for n in (2, 4):
            for case in CASE_NAMES:
                if case == "paper_2x2" and n != 2:
                    continue
                a, b, c = run_case(n, case)
                results.append((n, case, a, b, c))
        write_test_cases(results)
    elif len(args) == 2 and args[0] in ("2", "4"):
        run_case(int(args[0]), args[1])
    else:
        print(__doc__)
        sys.exit(1)


main()
