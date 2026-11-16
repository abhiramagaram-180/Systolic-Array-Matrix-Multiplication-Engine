#!/usr/bin/env python3
"""Bottom-up headless verification of logisim/systolic_gate_level.circ (Python 3 standard library only).

Usage (from the project root):
    python logisim/gate_generator/verify_gate_level.py            run every test
    python logisim/gate_generator/verify_gate_level.py fa mult    run only the named tests
    python logisim/gate_generator/verify_gate_level.py --file logisim/systolic_gate_level_w8.circ --w 8

It writes a Logisim "test vector" for each circuit, runs Logisim-evolution in its headless
mode (-w) and counts the rows that pass. Expected values come from plain Python
(closed-form model: after clock edge k, C[i][j] has added every product A[i][m]*B[m][j]
with i + j + m < k). The Logisim executable is searched in LOGISIM_EXE, then the default
install folders.
Tests: fa adder mult dff reg pe counter tdec select skew control feeder systolic top cases main negctl
"""
import argparse
import os
import random
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import make_cases_gate as cases      # noqa: E402

DEFAULT_FILE = os.path.join(os.path.dirname(HERE), "systolic_gate_level.circ")
EXE_CANDIDATES = [
    os.environ.get("LOGISIM_EXE", ""),
    r"C:\Program Files\logisim-evolution\logisim-evolution.exe",
    "/usr/bin/logisim-evolution",
    "/opt/logisim-evolution/bin/logisim-evolution",
]


def find_exe():
    for p in EXE_CANDIDATES:
        if p and os.path.exists(p):
            return p
    sys.exit("Logisim-evolution not found. Set LOGISIM_EXE to its path.")


# ------------------------------------------------------------------ test vectors
def fmt(v, width):
    if width == 1:
        return str(v & 1)
    return "0x%x" % v


class Vec:
    """Builds a Logisim test vector. Rows are applied in order on the same circuit state."""

    def __init__(self, ins, outs, sequential=True):
        self.ins, self.outs, self.sequential = ins, outs, sequential
        self.state = {n: 0 for n, _ in ins}
        self.rows = []
        self.seq = 0

    def header(self):
        cols = (["<set>", "<seq>"] if self.sequential else [])
        for n, w in self.ins + self.outs:
            cols.append(n if w == 1 else "%s[%d]" % (n, w))
        return " ".join(cols)

    def step(self, expect=None, **setv):
        """Apply the new input values (others keep their value) and optionally check outputs."""
        self.state.update(setv)
        expect = expect or {}
        toks = []
        if self.sequential:
            self.seq += 1
            toks += ["1", str(self.seq)]
        for n, w in self.ins:
            toks.append(fmt(self.state[n], w))
        for n, w in self.outs:
            toks.append(fmt(expect[n], w) if n in expect else "<dc>")
        self.rows.append(" ".join(toks))

    def edge(self, expect_after=None, **setv):
        """Clock pulse: set the inputs, rising edge, then falling edge. Outputs are checked after the rising edge."""
        self.step(None, clk=0, **setv)
        self.step(expect_after, clk=1)
        self.step(None, clk=0)

    def text(self):
        return self.header() + "\n" + "\n".join(self.rows) + "\n"


def run_vector(exe, circ_file, circuit, vec, retries=8, timeout=None):
    """Run a vector; returns (passed, failed, raw output).
    Logisim sometimes stalls (idle, no output) at start-up. A normal run takes a few seconds, so each
    attempt gets a short time limit (growing with the number of rows) and a stalled one is simply retried."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(vec.text())
        path = f.name
    if timeout is None:
        timeout = 45 + 0.2 * len(vec.rows)
    out = ""
    for attempt in range(retries):
        try:
            r = subprocess.run([exe, "-w", circuit, path, circ_file], capture_output=True, timeout=timeout)
            out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
            m = re.findall(r"Passed: (\d+), Failed: (\d+)", out)
            if m:
                os.unlink(path)
                return int(m[-1][0]), int(m[-1][1]), out
        except subprocess.TimeoutExpired:
            out = "timeout"
        time.sleep(2)
    os.unlink(path)
    return 0, -1, out


# ------------------------------------------------------------------ expected values
def c_after(a, b, k):
    """C matrix after k clock edges since the array was cleared (inputs skewed as in the design)."""
    return [[sum(a[i][m] * b[m][j] for m in range(4) if i + j + m < k) for j in range(4)] for i in range(4)]


def skewed(a, b, t, w):
    """Packed a_row_in / b_col_in values fed to the array during cycle t."""
    ra = sum((a[i][t - i] if 0 <= t - i < 4 else 0) << (i * w) for i in range(4))
    cb = sum((b[t - j][j] if 0 <= t - j < 4 else 0) << (j * w) for j in range(4))
    return ra, cb


# ------------------------------------------------------------------ the tests
class Suite:
    def __init__(self, args):
        self.exe = find_exe()
        self.file = os.path.abspath(args.file)
        self.w = args.w
        self.acc = cases.acc_width(args.w)
        self.maxv = (1 << self.w) - 1
        self.results = []
        self.rng = random.Random(2024)

    def go(self, name, circuit, vec):
        t0 = time.time()
        p, f, out = run_vector(self.exe, self.file, circuit, vec)
        ok = (f == 0 and p > 0)
        self.results.append((name, circuit, p, f, ok))
        print("%-34s %-14s passed %4d  failed %4d   %s   (%.0fs)" % (name, circuit, p, f, "OK" if ok else "**FAIL**",
                                                                    time.time() - t0))
        if not ok:
            print(out[:2500].encode("ascii", "replace").decode("ascii"))
        return ok

    # --- FA: all 8 inputs
    def t_fa(self):
        v = Vec([("a", 1), ("b", 1), ("cin", 1)], [("sum", 1), ("cout", 1)], sequential=False)
        for n in range(8):
            a, b, c = n >> 2 & 1, n >> 1 & 1, n & 1
            v.step({"sum": (a + b + c) & 1, "cout": (a + b + c) >> 1}, a=a, b=b, cin=c)
        self.go("FA: all 8 inputs", "FA", v)

    # --- adders
    def t_adder(self):
        for n in (self.w, self.acc):
            v = Vec([("a", n), ("b", n), ("cin", 1)], [("sum", n), ("cout", 1)], sequential=False)
            m = (1 << n) - 1
            if n <= 4:
                pairs = [(a, b, c) for a in range(m + 1) for b in range(m + 1) for c in (0, 1)]
            else:
                pairs = [(0, 0, 0), (m, m, 1), (m, 1, 0), (m, 0, 1), (1, m, 1), (m, m, 0)]
                pairs += [(self.rng.randint(0, m), self.rng.randint(0, m), self.rng.randint(0, 1)) for _ in range(300)]
            for a, b, c in pairs:
                s = a + b + c
                v.step({"sum": s & m, "cout": s >> n}, a=a, b=b, cin=c)
            self.go("ADDER_%d: %s" % (n, "all %d inputs" % len(pairs) if n <= 4 else "%d inputs incl. carries" % len(pairs)),
                    "ADDER_%d" % n, v)

    # --- multiplier: all pairs
    def t_mult(self):
        w = self.w
        v = Vec([("a", w), ("b", w)], [("p", 2 * w)], sequential=False)
        if w <= 5:
            pairs = [(a, b) for a in range(self.maxv + 1) for b in range(self.maxv + 1)]
            what = "all %d pairs" % len(pairs)
        else:       # wider than 5 bits: corners, powers of two and random pairs instead of every pair
            m = self.maxv
            pairs = [(0, 0), (m, m), (m, 1), (1, m), (m, 0), (0, m), (m, m - 1)]
            pairs += [(1 << i, 1 << j) for i in range(w) for j in range(w)]
            pairs += [(self.rng.randint(0, m), self.rng.randint(0, m)) for _ in range(400)]
            what = "%d pairs (corners, powers of two, random)" % len(pairs)
        for a, b in pairs:
            v.step({"p": a * b}, a=a, b=b)
        self.go("MULT_%dx%d: %s" % (w, w, what), "MULT_%dx%d" % (w, w), v)

    def t_dff(self):
        v = Vec([("clk", 1), ("D", 1)], [("Q", 1)])
        v.step({"Q": 0}, clk=0, D=0)
        v.step(None, D=1)
        v.step({"Q": 0})                    # D changes, no edge yet: Q holds
        v.step({"Q": 1}, clk=1)             # rising edge: Q takes D
        v.step({"Q": 1}, clk=0, D=0)        # falling edge and D change: Q holds
        v.step({"Q": 0}, clk=1)
        v.step({"Q": 0}, clk=0)
        self.go("DFF: edge triggered, holds", "DFF", v)

    def t_reg(self):
        for n in (self.w, self.acc):
            m = (1 << n) - 1
            v = Vec([("clk", 1), ("clear", 1), ("d", n)], [("q", n)])
            v.step({"q": 0}, clk=0, clear=0, d=0)
            vals = [9 & m, 6 & m, m, 1]
            prev = 0
            for x in vals:
                v.step({"q": prev}, clk=0, d=x)         # d set, no edge: q still old
                v.step({"q": x}, clk=1)                 # edge: q = d
                v.step({"q": x}, clk=0)
                prev = x
            v.step({"q": prev}, clk=0, clear=1, d=m)    # clear set, no edge yet: holds
            v.step({"q": 0}, clk=1)                     # edge with clear: 0 (not d)
            v.step({"q": 0}, clk=0, clear=0)
            v.step({"q": m}, clk=1)                     # edge: loads d again
            v.step({"q": m}, clk=0)
            self.go("REG_%d: load, hold, clear" % n, "REG_%d" % n, v)

    def t_pe(self):
        w, acc = self.w, self.acc
        v = Vec([("a_in", w), ("b_in", w), ("clk", 1), ("clear", 1)], [("a_out", w), ("b_out", w), ("acc", acc)])
        v.step(None, clk=0, clear=1, a_in=0, b_in=0)
        v.step({"acc": 0, "a_out": 0, "b_out": 0}, clk=1)                 # clear edge
        v.step(None, clk=0, clear=0, a_in=3, b_in=4)
        v.step({"acc": 12, "a_out": 3, "b_out": 4}, clk=1)                # a=3, b=4: 12 after one tick
        v.step(None, clk=0)
        v.step({"acc": 24, "a_out": 3, "b_out": 4}, clk=1)                # 24 after two
        total = 24
        for a, b in [(self.maxv, self.maxv), (0, 0), (5, self.maxv), (self.maxv, 0)]:
            v.step(None, clk=0, a_in=a, b_in=b)
            total += a * b
            v.step({"acc": total, "a_out": a, "b_out": b}, clk=1)
        v.step(None, clk=0, clear=1, a_in=7, b_in=7)                      # clear wins over data
        v.step({"acc": 0, "a_out": 0, "b_out": 0}, clk=1)
        v.step(None, clk=0, clear=0)
        total = 0
        for _ in range(4):                                                 # largest result 4*max*max
            v.step(None, clk=0, a_in=self.maxv, b_in=self.maxv)
            total += self.maxv * self.maxv
            v.step({"acc": total, "a_out": self.maxv, "b_out": self.maxv}, clk=1)
        v.step(None, clk=0)
        self.go("PE: 3x4 -> 12 -> 24, clear, max", "PE", v)

    def t_counter(self):
        v = Vec([("clk", 1), ("clear", 1), ("en", 1)], [("q", 4)])
        v.step(None, clk=0, clear=1, en=0)
        v.step({"q": 0}, clk=1)
        v.step(None, clk=0, clear=0, en=1)
        for k in range(1, 19):                       # counts up and wraps from 15 to 0
            v.step({"q": k % 16}, clk=1)
            v.step(None, clk=0)
        q = 18 % 16
        v.step(None, clk=0, en=0)
        for _ in range(3):                           # en = 0: holds
            v.step({"q": q}, clk=1)
            v.step(None, clk=0)
        v.step(None, clk=0, en=1, clear=1)           # clear wins over en
        v.step({"q": 0}, clk=1)
        v.step(None, clk=0, clear=0)
        v.step({"q": 1}, clk=1)
        v.step(None, clk=0)
        self.go("COUNTER4: count, wrap, hold, clear", "COUNTER4", v)

    def t_tdec(self):
        v = Vec([("t", 4)], [("sel", 4)], sequential=False)
        for t in range(16):
            v.step({"sel": (1 << t) if t < 4 else 0}, t=t)
        self.go("TDEC4: t = 0..15", "TDEC4", v)

    def t_select(self):
        w = self.w
        v = Vec([("sel", 4), ("din", 4 * w)], [("y", w)], sequential=False)
        for _ in range(60):
            vals = [self.rng.randint(0, self.maxv) for _ in range(4)]
            din = sum(x << (k * w) for k, x in enumerate(vals))
            for s in (0, 1, 2, 4, 8):
                y = 0 if s == 0 else vals[s.bit_length() - 1]
                v.step({"y": y}, sel=s, din=din)
        self.go("SELECT4: random data, all selects", "SELECT4", v)

    def t_skew(self):
        w = self.w
        for st in (1, 2, 3):
            v = Vec([("clk", 1), ("clear", 1), ("din", w)], [("dout", w)])
            v.step(None, clk=0, clear=1, din=0)
            v.step({"dout": 0}, clk=1)
            v.step(None, clk=0, clear=0)
            data = [self.rng.randint(1, self.maxv) for _ in range(8)] + [0, 0, 0, 0]
            hist = [0] * st                              # values inside the stages
            for x in data:
                v.step(None, clk=0, din=x)
                hist = [x] + hist[:-1]
                v.step({"dout": hist[-1]}, clk=1)        # output is the input from `st` edges ago
                v.step(None, clk=0)
            self.go("SKEW_%d: delays by %d edge(s)" % (st, st), "SKEW_%d" % st, v)

    def t_control(self):
        v = Vec([("clk", 1), ("rst", 1), ("start", 1)], [("t", 4), ("clear", 1), ("done", 1)])
        v.step(None, clk=0, rst=1, start=0)
        v.edge({"t": 0, "done": 0, "clear": 0})
        v.edge({"t": 0, "done": 0, "clear": 0})
        v.step({"t": 0, "done": 0, "clear": 0}, rst=0)
        for rep in range(2):          # two runs; the second one starts one tick after done
            idle = {"t": 0, "done": 0} if rep == 0 else {"t": 10, "done": 1}
            v.step(dict(idle, clear=1), clk=0, start=1)             # idle + start: clear = 1
            v.step(None, clk=1)                                      # start edge: run = 1, t = 0
            v.step({"clear": 0, "t": 0, "done": 0}, clk=0, start=0)
            for k in range(1, 11):
                if k == 4:
                    v.step({"clear": 0, "t": 3, "done": 0}, clk=0, start=1)    # start during a run is ignored
                v.edge({"t": k, "done": 1 if k == 10 else 0, "clear": 0})
                v.step(None, start=0)
            v.step({"done": 1, "clear": 0, "t": 10}, clk=0, start=1)           # start in the done cycle: no clear
            v.step(None, start=0)
            v.edge({"t": 10, "done": 1, "clear": 0})                            # run falls, counter holds at 10
        self.go("CONTROL: reset, 2 runs, t=10 done", "CONTROL", v)

    def t_feeder(self):
        w = self.w
        for name in ("hand_picked", "random"):
            a, b = cases.make_case(name, w)
            rows, colsv = cases.rows_packed(a, w), cases.cols_packed(b, w)
            ins = [("clk", 1), ("clear", 1), ("t", 4)] + [("A_row%d" % i, 4 * w) for i in range(4)] + \
                  [("B_col%d" % j, 4 * w) for j in range(4)]
            v = Vec(ins, [("a_row_in", 4 * w), ("b_col_in", 4 * w)])
            sets = {"A_row%d" % i: rows[i] for i in range(4)}
            sets.update({"B_col%d" % j: colsv[j] for j in range(4)})
            v.step(None, clk=0, clear=1, t=0, **sets)
            v.step(None, clk=1)
            v.step(None, clk=0, clear=0)
            for t in range(0, 11):
                ra, cb = skewed(a, b, t, w)
                v.step({"a_row_in": ra, "b_col_in": cb}, clk=0, t=t)
                v.step(None, clk=1)
                v.step(None, clk=0)
            self.go("FEEDER: skewed feed t=0..10 (%s)" % name, "FEEDER", v)

    def t_systolic(self):
        w, acc = self.w, self.acc
        for name in ("hand_picked", "all_max"):
            a, b = cases.make_case(name, w)
            ins = [("clk", 1), ("clear", 1), ("a_row_in", 4 * w), ("b_col_in", 4 * w)]
            outs = [("C%d%d" % (i, j), acc) for i in range(4) for j in range(4)]
            v = Vec(ins, outs)
            v.step(None, clk=0, clear=1, a_row_in=0, b_col_in=0)
            v.step({o: 0 for o, _ in outs}, clk=1)
            v.step(None, clk=0, clear=0)
            for t in range(0, 12):
                ra, cb = skewed(a, b, t, w)
                v.step(None, clk=0, a_row_in=ra, b_col_in=cb)
                c = c_after(a, b, t + 1)
                v.step({"C%d%d" % (i, j): c[i][j] for i in range(4) for j in range(4)}, clk=1)
                v.step(None, clk=0)
            self.go("SYSTOLIC_4x4: every cycle (%s)" % name, "SYSTOLIC_4x4", v)

    def top_vec(self):
        w, acc = self.w, self.acc
        ins = [("clk", 1), ("rst", 1), ("start", 1)] + [("A_row%d" % i, 4 * w) for i in range(4)] + \
              [("B_col%d" % j, 4 * w) for j in range(4)]
        outs = [("done", 1), ("t", 4)] + [("C%d%d" % (i, j), acc) for i in range(4) for j in range(4)]
        v = Vec(ins, outs)
        v.step(None, clk=0, rst=1, start=0)
        v.edge()
        v.edge()
        v.step(None, rst=0)
        return v

    def top_run(self, v, a, b, wrong=None):
        """Append: set matrices, one idle edge, start pulse, 10 cycles, checking t, done and C after every edge."""
        w, acc = self.w, self.acc
        rows, colsv = cases.rows_packed(a, w), cases.cols_packed(b, w)
        sets = {"A_row%d" % i: rows[i] for i in range(4)}
        sets.update({"B_col%d" % j: colsv[j] for j in range(4)})
        v.step(None, clk=0, start=0, **sets)
        v.edge()                                           # one tick after the previous done: run falls
        v.step(None, clk=0, start=1)                       # start = 1 for one clock cycle
        v.step(None, clk=1)
        v.step({"done": 0, "t": 0}, clk=0, start=0)
        for k in range(1, 11):
            c = c_after(a, b, k)
            exp = {"done": 1 if k == 10 else 0, "t": k}
            exp.update({"C%d%d" % (i, j): c[i][j] for i in range(4) for j in range(4)})
            if wrong and k == 10:
                exp["C23"] += 1                            # negative control: must fail
            v.step(None, clk=0)
            v.step(exp, clk=1)
            v.step(None, clk=0)

    def t_top(self):
        w = self.w
        for name in cases.case_names():
            a, b = cases.make_case(name, w)
            v = self.top_vec()
            self.top_run(v, a, b)
            self.top_run(v, a, b)                          # second run without reset
            self.go("TOP: %s, 2 back-to-back runs" % name, "TOP", v)
        v = self.top_vec()
        for _ in range(20):
            a = [[self.rng.randint(0, self.maxv) for _ in range(4)] for _ in range(4)]
            b = [[self.rng.randint(0, self.maxv) for _ in range(4)] for _ in range(4)]
            self.top_run(v, a, b)
        self.go("TOP: 20 random matrices in a row", "TOP", v)

    def t_cases(self):
        """Wrapper circuits with hard-wired constants."""
        w, acc = self.w, self.acc
        for name in cases.case_names():
            a, b = cases.make_case(name, w)
            outs = [("done", 1), ("t", 4)] + [("C%d%d" % (i, j), acc) for i in range(4) for j in range(4)]
            v = Vec([("clk", 1), ("rst", 1), ("start", 1)], outs)
            v.step(None, clk=0, rst=1, start=0)
            v.edge()
            v.edge()
            v.step(None, rst=0)
            for rep in range(2):
                v.edge()
                v.step(None, clk=0, start=1)
                v.step(None, clk=1)
                v.step(None, clk=0, start=0)
                for k in range(1, 11):
                    c = c_after(a, b, k)
                    exp = {"done": 1 if k == 10 else 0, "t": k}
                    exp.update({"C%d%d" % (i, j): c[i][j] for i in range(4) for j in range(4)})
                    v.step(None, clk=0)
                    v.step(exp, clk=1)
                    v.step(None, clk=0)
            self.go("case_%s wrapper, 2 runs" % name, "case_" + name, v)

    def t_main(self):
        """The demo circuit 'main' with its REAL Clock component, in Logisim's tty mode.
        A throwaway copy ties start to 1 and rst to 0 and adds an output pin 'halt' on done."""
        w = self.w
        text = open(self.file, encoding="utf-8").read()
        m = re.search(r'  <circuit name="main">.*?  </circuit>\n', text, re.S)
        blk = m.group(0)
        new = blk
        for label, val in (("rst", 0), ("start", 1)):
            pm = re.search(r'    <comp lib="0" loc="\((\d+),(\d+)\)" name="Pin">\n(?:      <a name="[^"]+" val="[^"]*"/>\n)*?'
                           r'      <a name="label" val="%s"/>\n(?:      <a name="[^"]+" val="[^"]*"/>\n)*?    </comp>\n' % label, new)
            assert pm, "pin " + label
            const = ('    <comp lib="0" loc="(%s,%s)" name="Constant">\n      <a name="value" val="0x%x"/>\n    </comp>\n'
                     % (pm.group(1), pm.group(2), val))
            new = new.replace(pm.group(0), const)
        extra = ('    <comp lib="0" loc="(200,4000)" name="Tunnel">\n      <a name="label" val="done"/>\n    </comp>\n'
                 '    <comp lib="0" loc="(260,4000)" name="Pin">\n      <a name="appearance" val="classic"/>\n'
                 '      <a name="facing" val="west"/>\n      <a name="label" val="halt"/>\n'
                 '      <a name="type" val="output"/>\n    </comp>\n'
                 '    <wire from="(200,4000)" to="(260,4000)"/>\n')
        new = new.replace("  </circuit>\n", extra + "  </circuit>\n")
        with tempfile.NamedTemporaryFile("w", suffix=".circ", delete=False, encoding="utf-8") as f:
            f.write(text.replace(blk, new))
            path = f.name
        a, b = cases.make_case("hand_picked", w)
        c = c_after(a, b, 10)
        r = None
        for attempt in range(8):
            try:
                r = subprocess.run([self.exe, "-t", "table,halt", "--toplevel-circuit", "main", path],
                                   capture_output=True, timeout=60)
                if r.stdout.strip():
                    break
            except subprocess.TimeoutExpired:
                time.sleep(2)
        os.unlink(path)
        rows = r.stdout.decode("utf-8", "replace").strip().split(chr(10)) if r else []
        ok = False
        if rows:
            last = rows[-1].split(chr(9))
            done = last[0].strip()
            vals = [int(x.replace(" ", ""), 2) for x in last[1:]]
            flat = [c[i][j] for i in range(4) for j in range(4)]
            first_done = [i for i, line in enumerate(rows) if line.split(chr(9))[0].strip() == "1"]
            ok = done == "1" and vals == flat and first_done == [len(rows) - 1]
            print("%-34s %-14s rows %d, done only in last row: %s, C equals expected: %s   %s"
                  % ("main: real Clock, tty mode", "main", len(rows), first_done == [len(rows) - 1], vals == flat,
                     "OK" if ok else "**FAIL**"))
        else:
            print("main tty run produced no output  **FAIL**")
        self.results.append(("main (Clock, tty)", "main", len(rows), 0 if ok else 1, ok))

    def t_negctl(self):
        a, b = cases.make_case("hand_picked", self.w)
        v = self.top_vec()
        self.top_run(v, a, b, wrong=True)
        p, f, out = run_vector(self.exe, self.file, "TOP", v)
        ok = f > 0
        self.results.append(("negative control (wrong C23)", "TOP", p, f, ok))
        print("%-34s %-14s passed %4d  failed %4d   %s" % ("NEGATIVE CONTROL: wrong C23", "TOP", p, f,
                                                          "OK (it fails, as it must)" if ok else "**BAD: wrong value passed**"))


ORDER = ["fa", "adder", "mult", "dff", "reg", "pe", "counter", "tdec", "select", "skew", "control",
         "feeder", "systolic", "top", "cases", "main", "negctl"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tests", nargs="*")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--w", type=int, default=4)
    args = ap.parse_args()
    s = Suite(args)
    for name in (args.tests or ORDER):
        getattr(s, "t_" + name)()
    bad = [r for r in s.results if not r[4]]
    print("\n%d test runs, %d failed" % (len(s.results), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
