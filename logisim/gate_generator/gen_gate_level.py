#!/usr/bin/env python3
"""Generate the gate-level Logisim circuit logisim/systolic_gate_level.circ.

Usage (from the project root):
    python logisim/gate_generator/gen_gate_level.py              W = 4, 10-bit accumulators
    python logisim/gate_generator/gen_gate_level.py --w 8 --acc 20 --out logisim/systolic_gate_level_w8.circ

Only these Logisim parts are used (Logisim-evolution v5.0.0):
    Gates   : NOT, AND, OR, XOR
    Wiring  : Pin, Constant, Splitter, Tunnel, Clock, Ground
    Memory  : D Flip-Flop (only inside the circuit named DFF)
    Display : LED, Hex Digit Display
No Arithmetic, Plexers, Register, Counter, ROM, RAM, TTL parts.

The circuit hierarchy mirrors rtl_gate/ (the structural Verilog):
    FA, ADDER_n, MULT_4x4, DFF, REG_n, PE, COUNTER4, TDEC4, SELECT4, SKEW_k,
    CONTROL, FEEDER, SYSTOLIC_4x4, TOP, main, and one wrapper per test case.
Subcircuit names carry the width when it matters (ADDER_4, ADDER_10, REG_4, REG_10).

Layout rules: inputs on the left, outputs on the right. Gates, flip-flops and
subcircuit boxes are connected with a short wire to a labelled Tunnel; two ports
with the same tunnel label are connected. Nothing is routed across other wires.

Port positions (relative to the part's location) were taken from the Logisim
source code and proved by simulation (see verify_gate_level.py):
    AND/OR gate : inputs (-50,-20) (-50,+20), output (0,0)
    XOR gate    : inputs (-60,-20) (-60,+20), output (0,0)
    NOT gate    : input (-30,0), output (0,0)
    D flip-flop (classic look): CK (-40,0), D (-40,20), Q (0,0), Q-bar (0,20), reset (-10,30), preset (-30,30)
    Splitter    : combined end at (0,0), the other ends at x = +20 (facing east) or -20 (facing west),
                  y = -20*(fanout//2) + 20*i   (spacing 2, centred)
    Subcircuit box (fixed-size, logisim_evolution look): inputs at (-220, 20*k), outputs at (0, 20*k),
                  in the top-to-bottom order of the pins inside the subcircuit
"""
import argparse
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import make_cases_gate as cases      # noqa: E402

BOX_W = 220           # width of a fixed-size subcircuit box
PIN_DY = 20           # vertical distance between box ports

# library numbers inside the generated file (only the libraries we use are loaded)
LIB_WIRING, LIB_GATES, LIB_MEMORY, LIB_IO = 0, 1, 2, 3

GATE_IN_DX = {"AND": 50, "OR": 50, "XOR": 60}


class Port:
    """A connection point: position, the side the stub wire leaves to, and the bit width."""
    __slots__ = ("x", "y", "side", "w", "name")

    def __init__(self, x, y, side, w, name=""):
        self.x, self.y, self.side, self.w, self.name = x, y, side, w, name


class Sub:
    """What an instance of a subcircuit looks like from outside (pins in box order)."""

    def __init__(self, name, ins, outs):
        self.name = name
        self.ins = ins        # [(label, width)] top to bottom
        self.outs = outs

    def ports(self, x, y):
        d = {}
        for k, (lab, w) in enumerate(self.ins):
            d[lab] = Port(x - BOX_W, y + PIN_DY * k, "W", w, lab)
        for k, (lab, w) in enumerate(self.outs):
            d[lab] = Port(x, y + PIN_DY * k, "E", w, lab)
        return d


SUBS = {}


def xml_attrs(attrs):
    return "".join('      <a name="%s" val="%s"/>\n' % (k, v) for k, v in attrs)


class Circuit:
    def __init__(self, name):
        self.name = name
        self.comps = []
        self.wires = []
        self.pins_in = []       # (label, width, y)
        self.pins_out = []
        self.gates = Counter()  # AND/OR/XOR/NOT/DFF created directly in this circuit
        self.insts = Counter()  # subcircuit name -> number of instances
        self.net_use = Counter()

    # ---------------------------------------------------------------- raw parts
    def comp(self, lib, loc, name, attrs=()):
        lib_txt = ' lib="%d"' % lib if lib is not None else ""
        if attrs:
            self.comps.append('    <comp%s loc="(%d,%d)" name="%s">\n%s    </comp>\n'
                              % (lib_txt, loc[0], loc[1], name, xml_attrs(attrs)))
        else:
            self.comps.append('    <comp%s loc="(%d,%d)" name="%s"/>\n' % (lib_txt, loc[0], loc[1], name))

    def wire(self, *pts):
        for a, b in zip(pts, pts[1:]):
            assert a[0] == b[0] or a[1] == b[1], "diagonal wire %s %s" % (a, b)
            assert a != b
            self.wires.append('    <wire from="(%d,%d)" to="(%d,%d)"/>\n' % (a[0], a[1], b[0], b[1]))

    def tunnel(self, x, y, label, facing, width):
        attrs = []
        if facing != "east":
            attrs.append(("facing", facing))
        attrs.append(("label", label))
        if width != 1:
            attrs.append(("width", str(width)))
        self.comp(LIB_WIRING, (x, y), "Tunnel", attrs)

    # ------------------------------------------------------------------- pins
    def pin_in(self, label, width, x, y):
        attrs = [("appearance", "classic"), ("label", label)]
        if width != 1:
            attrs.append(("width", str(width)))
        self.comp(LIB_WIRING, (x, y), "Pin", attrs)
        self.pins_in.append((label, width, y))
        return Port(x, y, "E", width, label)

    def pin_out(self, label, width, x, y, radix=None):
        attrs = [("appearance", "classic"), ("facing", "west"), ("label", label)]
        if radix:
            attrs.append(("radix", radix))
        attrs.append(("type", "output"))
        if width != 1:
            attrs.append(("width", str(width)))
        self.comp(LIB_WIRING, (x, y), "Pin", attrs)
        self.pins_out.append((label, width, y))
        return Port(x, y, "W", width, label)

    # ------------------------------------------------------------------ gates
    def gate(self, kind, x, y, label):
        """2-input AND / OR / XOR. Returns (in1, in2, out)."""
        d = GATE_IN_DX[kind]
        self.comp(LIB_GATES, (x, y), kind + " Gate", [("label", label)])
        self.gates[kind] += 1
        return (Port(x - d, y - 20, "W", 1, label + ".a"), Port(x - d, y + 20, "W", 1, label + ".b"),
                Port(x, y, "E", 1, label + ".y"))

    def not_gate(self, x, y, label):
        self.comp(LIB_GATES, (x, y), "NOT Gate", [("label", label)])
        self.gates["NOT"] += 1
        return Port(x - 30, y, "W", 1, label + ".a"), Port(x, y, "E", 1, label + ".y")

    def dff_part(self, x, y, label):
        """The Logisim D flip-flop (classic look). Returns ck, d, q, qbar, reset, preset ports."""
        self.comp(LIB_MEMORY, (x, y), "D Flip-Flop", [("appearance", "classic"), ("label", label)])
        self.gates["DFF"] += 1
        return dict(ck=Port(x - 40, y, "W", 1), d=Port(x - 40, y + 20, "W", 1), q=Port(x, y, "E", 1),
                    qbar=Port(x, y + 20, "E", 1), reset=Port(x - 10, y + 30, "S", 1),
                    preset=Port(x - 30, y + 30, "S", 1))

    # -------------------------------------------------- constants, splitters
    def const(self, x, y, width, value):
        self.comp(LIB_WIRING, (x, y), "Constant", [("value", "0x%x" % value), ("width", str(width))])
        return Port(x, y, "E", width)

    def ground(self, x, y):
        self.comp(LIB_WIRING, (x, y), "Ground")
        return Port(x, y, "E", 1)

    def splitter(self, x, y, facing, fanout, incoming):
        """Returns (combined_port, [end ports]). Bit groups are contiguous: end e carries bits [e*w_end +: w_end]."""
        assert incoming % fanout == 0
        w_end = incoming // fanout
        attrs = []
        if facing != "east":
            attrs.append(("facing", facing))
        attrs += [("appear", "center"), ("fanout", str(fanout)), ("incoming", str(incoming)), ("spacing", "2")]
        if fanout < incoming:
            # Several bits per end (a "lane"). Logisim does not rebuild the bit-to-end table correctly when
            # the file only gives fanout and incoming, so every bit is assigned explicitly (0 = first end).
            attrs += [("bit%d" % b, str(b // w_end)) for b in range(incoming)]
        self.comp(LIB_WIRING, (x, y), "Splitter", attrs)
        ex = x + 20 if facing == "east" else x - 20
        eside = "E" if facing == "east" else "W"
        cside = "W" if facing == "east" else "E"
        ends = [Port(ex, y - 20 * (fanout // 2) + 20 * i, eside, w_end) for i in range(fanout)]
        return Port(x, y, cside, incoming), ends

    # -------------------------------------------------------------- instances
    def inst(self, sub, x, y, label):
        s = SUBS[sub]
        # Logisim-evolution 5.0.0 hangs while loading a file when an instance label equals the name of
        # a circuit (ignoring upper/lower case), e.g. instance "control" of circuit CONTROL.
        # So every such label gets the prefix "u_" (for "unit").
        if label.lower() in [n.lower() for n in SUBS] or label.lower() == self.name.lower():
            label = "u_" + label
        self.comp(None, (x, y), sub, [("label", label)])
        self.insts[sub] += 1
        return s.ports(x, y)

    # ------------------------------------------------------------------- nets
    def net(self, label, *ports):
        """Connect ports by giving each one a stub wire and a tunnel with the same label."""
        w = ports[0].w
        for p in ports:
            assert p.w == w, "width mismatch on net %s in %s: %s vs %s" % (label, self.name, p.w, w)
            length = 30 if (p.y // 20) % 2 == 0 else 90
            if p.side == "W":
                end = (p.x - length, p.y)
                self.wire((p.x, p.y), end)
                self.tunnel(end[0], end[1], label, "east", w)
            elif p.side == "E":
                end = (p.x + length, p.y)
                self.wire((p.x, p.y), end)
                self.tunnel(end[0], end[1], label, "west", w)
            else:           # "S": stub goes down (only used for flip-flop reset/preset, tied to Ground)
                raise ValueError("use direct wires for S ports")
        self.net_use[label] += len(ports)

    def nc(self, label, port):
        """An output that is intentionally not used: stub and a tunnel named nc_..."""
        self.net("nc_" + label, port)

    # ---------------------------------------------------------------- output
    def to_xml(self):
        head = ('  <circuit name="%s">\n    <a name="appearance" val="logisim_evolution"/>\n'
                '    <a name="circuit" val="%s"/>\n    <a name="circuitnamedboxfixedsize" val="true"/>\n'
                '    <a name="simulationFrequency" val="1.0"/>\n' % (self.name, self.name))
        return head + "".join(self.comps) + "".join(self.wires) + "  </circuit>\n"

    def register_sub(self):
        ins = [(lab, w) for lab, w, y in sorted(self.pins_in, key=lambda t: t[2])]
        outs = [(lab, w) for lab, w, y in sorted(self.pins_out, key=lambda t: t[2])]
        ys = [y for _, _, y in self.pins_in] + [y for _, _, y in self.pins_out]
        assert len(set(y for _, _, y in self.pins_in)) == len(self.pins_in), "pins share a y in " + self.name
        assert len(set(y for _, _, y in self.pins_out)) == len(self.pins_out), "output pins share a y in " + self.name
        SUBS[self.name] = Sub(self.name, ins, outs)


CIRCUITS = []         # in definition order (dependencies first)


def finish(c):
    c.register_sub()
    CIRCUITS.append(c)
    return c


# =============================================================================
# small helper: bit labels
# =============================================================================
def bit(prefix, *idx):
    return prefix + "_" + "_".join(str(i) for i in idx)


def pin_column(c, ins, outs, x_in=100, x_out=3200, y0=100, dy=60):
    """Create the pins of a circuit in the given order. ins/outs: [(label, width[, radix])]."""
    pi, po = {}, {}
    for k, spec in enumerate(ins):
        pi[spec[0]] = c.pin_in(spec[0], spec[1], x_in, y0 + dy * k)
    for k, spec in enumerate(outs):
        radix = spec[2] if len(spec) > 2 else None
        po[spec[0]] = c.pin_out(spec[0], spec[1], x_out, y0 + dy * k, radix)
    return pi, po


# =============================================================================
# the circuits
# =============================================================================
def build_fa():
    c = Circuit("FA")
    pi, po = pin_column(c, [("a", 1), ("b", 1), ("cin", 1)], [("sum", 1), ("cout", 1)], x_out=1900)
    x1a, x1b, x1y = c.gate("XOR", 700, 100, "xor1_a_xor_b")
    x2a, x2b, x2y = c.gate("XOR", 1300, 100, "xor2_sum")
    a1a, a1b, a1y = c.gate("AND", 700, 400, "and1_a_and_b")
    a2a, a2b, a2y = c.gate("AND", 1300, 400, "and2_t_and_cin")
    oa, ob, oy = c.gate("OR", 1700, 400, "or_cout")
    c.net("a", pi["a"], x1a, a1a)
    c.net("b", pi["b"], x1b, a1b)
    c.net("cin", pi["cin"], x2b, a2b)
    c.net("t", x1y, x2a, a2a)               # t = a XOR b
    c.net("sum", x2y, po["sum"])
    c.net("g", a1y, oa)                     # g = a AND b
    c.net("p", a2y, ob)                     # p = t AND cin
    c.net("cout", oy, po["cout"])
    return finish(c)


def build_dff():
    """The only circuit that contains a Logisim flip-flop. Pins are wired straight to the part."""
    c = Circuit("DFF")
    clk = c.pin_in("clk", 1, 100, 120)
    d = c.pin_in("D", 1, 100, 140)
    q = c.pin_out("Q", 1, 500, 120)
    ff = c.dff_part(300, 120, "dff")
    c.wire((clk.x, clk.y), (ff["ck"].x, ff["ck"].y))
    c.wire((d.x, d.y), (ff["d"].x, ff["d"].y))
    c.wire((ff["q"].x, ff["q"].y), (q.x, q.y))
    # reset and preset are not used: tie both to ground (0)
    c.ground(280, 200)
    c.wire((ff["reset"].x, ff["reset"].y), (ff["reset"].x, 200), (280, 200))
    c.wire((ff["preset"].x, ff["preset"].y), (ff["preset"].x, 200), (280, 200))
    c.net("nc_qbar", ff["qbar"])
    return finish(c)


def build_adder(n):
    name = "ADDER_%d" % n
    c = Circuit(name)
    pi, po = pin_column(c, [("a", n), ("b", n), ("cin", 1)], [("sum", n), ("cout", 1)], x_out=2900)
    ys = 400
    comb_a, ends_a = c.splitter(450, ys, "east", n, n)
    comb_b, ends_b = c.splitter(450, ys + 20 * n + 300, "east", n, n)
    c.net("a", pi["a"], comb_a)
    c.net("b", pi["b"], comb_b)
    c.net("c0", pi["cin"])      # the carry into bit 0 is the cin pin
    comb_s, ends_s = c.splitter(2500, ys, "west", n, n)
    for i in range(n):
        c.net(bit("a", i), ends_a[i])
        c.net(bit("b", i), ends_b[i])
    # FA column
    for i in range(n):
        p = c.inst("FA", 1700, 300 + 140 * i, "fa%d" % i)
        c.net(bit("a", i), p["a"])
        c.net(bit("b", i), p["b"])
        c.net("c%d" % i, p["cin"])
        c.net(bit("s", i), p["sum"])
        c.net("c%d" % (i + 1), p["cout"])
    for i in range(n):
        c.net(bit("s", i), ends_s[i])
    c.net("sum", comb_s, po["sum"])
    c.net("c%d" % n, po["cout"])
    return finish(c)


def build_mult(w):
    name = "MULT_%dx%d" % (w, w)
    c = Circuit(name)
    pi, po = pin_column(c, [("a", w), ("b", w)], [("p", 2 * w)], x_out=5600)
    comb_a, ends_a = c.splitter(450, 400, "east", w, w)
    comb_b, ends_b = c.splitter(450, 400 + 20 * w + 300, "east", w, w)
    c.net("a", pi["a"], comb_a)
    c.net("b", pi["b"], comb_b)
    for k in range(w):
        c.net(bit("a", k), ends_a[k])
        c.net(bit("b", k), ends_b[k])
    gnd = c.ground(1200, 100)
    c.net("zero", gnd)

    def s(j, k):            # sum bit k of row j (row 0 is the partial product itself)
        return bit("pp", 0, k) if j == 0 else bit("s", j, k)

    def cout(j):            # carry-out of row j (row 0 has none)
        return "zero" if j == 0 else "c_%d" % j

    band = 100 * w + 200
    for j in range(w):
        y0 = 300 + band * j
        for k in range(w):
            ga, gb, gy = c.gate("AND", 1500, y0 + 100 * k, "and_b%d_a%d" % (j, k))
            c.net(bit("a", k), ga)
            c.net(bit("b", j), gb)
            c.net(bit("pp", j, k), gy)
    for j in range(1, w):
        y0 = 300 + band * j
        # partial product bits -> bus
        comb_pp, ends_pp = c.splitter(2300, y0 + 40, "west", w, w)
        for k in range(w):
            c.net(bit("pp", j, k), ends_pp[k])
        c.net("ppbus_%d" % j, comb_pp)
        # shifted previous sum: {carry of row j-1, sum bits 1..w-1 of row j-1}
        comb_up, ends_up = c.splitter(2300, y0 + 240, "west", w, w)
        for k in range(w - 1):
            c.net(s(j - 1, k + 1), ends_up[k])
        c.net(cout(j - 1), ends_up[w - 1])
        c.net("upbus_%d" % j, comb_up)
        p = c.inst("ADDER_%d" % w, 3500, y0 + 100, "add_row%d" % j)
        c.net("upbus_%d" % j, p["a"])
        c.net("ppbus_%d" % j, p["b"])
        c.net("zero", p["cin"])
        c.net("sumbus_%d" % j, p["sum"])
        c.net("c_%d" % j, p["cout"])
        comb_s, ends_s = c.splitter(4300, y0 + 100, "east", w, w)
        c.net("sumbus_%d" % j, comb_s)
        for k in range(w):
            c.net(bit("s", j, k), ends_s[k])
    # product bits
    comb_p, ends_p = c.splitter(5000, 700, "west", 2 * w, 2 * w)
    for m in range(2 * w):
        if m < w:
            lab = s(m, 0)
        elif m < 2 * w - 1:
            lab = s(w - 1, m - w + 1)
        else:
            lab = cout(w - 1)
        c.net(lab, ends_p[m])
    c.net("p", comb_p, po["p"])
    return finish(c)


def build_reg(n):
    name = "REG_%d" % n
    c = Circuit(name)
    pi, po = pin_column(c, [("clk", 1), ("clear", 1), ("d", n)], [("q", n)], x_out=2900)
    comb_d, ends_d = c.splitter(450, 600, "east", n, n)
    comb_q, ends_q = c.splitter(2500, 600, "west", n, n)
    c.net("d", pi["d"], comb_d)
    c.net("q", comb_q, po["q"])
    c.net("clk", pi["clk"])
    c.net("clear", pi["clear"])
    ni, no = c.not_gate(900, 100, "not_clear")
    c.net("clear", ni)
    c.net("not_clear", no)
    for i in range(n):
        c.net(bit("d", i), ends_d[i])
        ga, gb, gy = c.gate("AND", 1100, 300 + 140 * i, "and_d%d" % i)
        c.net(bit("d", i), ga)
        c.net("not_clear", gb)
        c.net(bit("dg", i), gy)
        f = c.inst("DFF", 1900, 300 + 140 * i, "dff%d" % i)
        c.net("clk", f["clk"])
        c.net(bit("dg", i), f["D"])
        c.net(bit("q", i), f["Q"])
        c.net(bit("q", i), ends_q[i])
    return finish(c)


def build_pe(w, acc):
    c = Circuit("PE")
    pi, po = pin_column(c, [("a_in", w), ("b_in", w), ("clk", 1), ("clear", 1)],
                        [("a_out", w), ("b_out", w), ("acc", acc)], x_out=5200)
    m = c.inst("MULT_%dx%d" % (w, w), 1200, 200, "mult")
    c.net("a_in", pi["a_in"], m["a"])
    c.net("b_in", pi["b_in"], m["b"])
    c.net("product", m["p"])
    # product bits, then pad with zeros up to the accumulator width
    comb_split, ends_split = c.splitter(1800, 500, "east", 2 * w, 2 * w)
    c.net("product", comb_split)
    comb_ext, ends_ext = c.splitter(2600, 500, "west", acc, acc)
    gnd = c.ground(2200, 100)
    c.net("zero", gnd)
    for i in range(2 * w):
        c.net(bit("pb", i), ends_split[i])
        c.net(bit("pb", i), ends_ext[i])
    for i in range(2 * w, acc):
        c.net("zero", ends_ext[i])
    c.net("product_ext", comb_ext)
    add = c.inst("ADDER_%d" % acc, 3500, 300, "acc_adder")
    c.net("acc", add["a"], po["acc"])
    c.net("product_ext", add["b"])
    c.net("zero", add["cin"])
    c.net("sum", add["sum"])
    c.nc("add_cout", add["cout"])
    ra = c.inst("REG_%d" % acc, 4400, 300, "acc_reg")
    c.net("clk", ra["clk"], pi["clk"])
    c.net("clear", ra["clear"], pi["clear"])
    c.net("sum", ra["d"])
    c.net("acc", ra["q"])
    r1 = c.inst("REG_%d" % w, 4400, 800, "a_reg")
    c.net("clk", r1["clk"])
    c.net("clear", r1["clear"])
    c.net("a_in", r1["d"])
    c.net("a_out", r1["q"], po["a_out"])
    r2 = c.inst("REG_%d" % w, 4400, 1100, "b_reg")
    c.net("clk", r2["clk"])
    c.net("clear", r2["clear"])
    c.net("b_in", r2["d"])
    c.net("b_out", r2["q"], po["b_out"])
    return finish(c)


def build_counter4():
    c = Circuit("COUNTER4")
    pi, po = pin_column(c, [("clk", 1), ("clear", 1), ("en", 1)], [("q", 4)], x_out=3100)
    comb_q, ends_q = c.splitter(450, 600, "east", 4, 4)
    # toggle chain: tg0 = en, tg1 = en AND q0, tg2 = tg1 AND q1, tg3 = tg2 AND q2
    a1 = c.gate("AND", 1100, 300, "and_tg1")
    a2 = c.gate("AND", 1100, 500, "and_tg2")
    a3 = c.gate("AND", 1100, 700, "and_tg3")
    c.net("en", pi["en"], a1[0])
    c.net("tg1", a1[2], a2[0])
    c.net("tg2", a2[2], a3[0])
    c.net("tg3", a3[2])
    c.net("q_0", ends_q[0], a1[1])
    c.net("q_1", ends_q[1], a2[1])
    c.net("q_2", ends_q[2], a3[1])
    c.net("q_3", ends_q[3])
    # next value: bit i flips when its toggle line is 1
    comb_n, ends_n = c.splitter(2300, 600, "west", 4, 4)
    xs = []
    for i in range(4):
        xs.append(c.gate("XOR", 1700, 150 + 200 * i, "xor_next%d" % i))
    c.net("q_0", xs[0][0])
    c.net("en", xs[0][1])
    c.net("q_1", xs[1][0])
    c.net("tg1", xs[1][1])
    c.net("q_2", xs[2][0])
    c.net("tg2", xs[2][1])
    c.net("q_3", xs[3][0])
    c.net("tg3", xs[3][1])
    for i in range(4):
        c.net(bit("nx", i), xs[i][2], ends_n[i])
    c.net("next", comb_n)
    r = c.inst("REG_4", 2900, 900, "state_reg")
    c.net("clk", pi["clk"], r["clk"])
    c.net("clear", pi["clear"], r["clear"])
    c.net("next", r["d"])
    c.net("q", r["q"], po["q"], comb_q)
    return finish(c)


def build_tdec4():
    c = Circuit("TDEC4")
    pi, po = pin_column(c, [("t", 4)], [("sel", 4)], x_out=3300)
    comb_t, ends_t = c.splitter(450, 600, "east", 4, 4)
    c.net("t", pi["t"], comb_t)
    for i in range(4):
        c.net(bit("t", i), ends_t[i])
    nots = []
    for i in range(4):
        nots.append(c.not_gate(900, 200 + 100 * i, "not_t%d" % i))
        c.net(bit("t", i), nots[i][0])
        c.net(bit("nt", i), nots[i][1])
    lt = c.gate("AND", 1500, 200, "and_lt4")                  # t < 4
    c.net(bit("nt", 3), lt[0])
    c.net(bit("nt", 2), lt[1])
    c.net("lt4", lt[2])
    low_in = [("nt_1", "nt_0"), ("nt_1", "t_0"), ("t_1", "nt_0"), ("t_1", "t_0")]
    for k in range(4):
        g = c.gate("AND", 1500, 500 + 200 * k, "and_low%d" % k)
        c.net(low_in[k][0], g[0])
        c.net(low_in[k][1], g[1])
        c.net(bit("low", k), g[2])
    comb_s, ends_s = c.splitter(2900, 800, "west", 4, 4)
    for k in range(4):
        g = c.gate("AND", 2300, 500 + 200 * k, "and_sel%d" % k)
        c.net("lt4", g[0])
        c.net(bit("low", k), g[1])
        c.net(bit("sel", k), g[2], ends_s[k])
    c.net("sel", comb_s, po["sel"])
    return finish(c)


def build_select4(w):
    c = Circuit("SELECT4")
    pi, po = pin_column(c, [("sel", 4), ("din", 4 * w)], [("y", w)], x_out=3700)
    comb_s, ends_s = c.splitter(450, 400, "east", 4, 4)
    comb_d, ends_d = c.splitter(450, 400 + 20 * 4 * w + 400, "east", 4 * w, 4 * w)
    c.net("sel", pi["sel"], comb_s)
    c.net("din", pi["din"], comb_d)
    for k in range(4):
        c.net(bit("s", k), ends_s[k])
    for k in range(4):
        for b in range(w):
            c.net(bit("d", k, b), ends_d[k * w + b])
    comb_y, ends_y = c.splitter(3300, 800, "west", w, w)
    band = 500
    for b in range(w):
        y0 = 200 + band * b
        for k in range(4):
            g = c.gate("AND", 1500, y0 + 100 * k, "and_k%d_b%d" % (k, b))
            c.net(bit("s", k), g[0])
            c.net(bit("d", k, b), g[1])
            c.net(bit("pick", k, b), g[2])
        o01 = c.gate("OR", 2200, y0 + 50, "or01_b%d" % b)
        o23 = c.gate("OR", 2200, y0 + 250, "or23_b%d" % b)
        oy = c.gate("OR", 2800, y0 + 150, "or_y_b%d" % b)
        c.net(bit("pick", 0, b), o01[0])
        c.net(bit("pick", 1, b), o01[1])
        c.net(bit("pick", 2, b), o23[0])
        c.net(bit("pick", 3, b), o23[1])
        c.net(bit("or01", b), o01[2], oy[0])
        c.net(bit("or23", b), o23[2], oy[1])
        c.net(bit("y", b), oy[2], ends_y[b])
    c.net("y", comb_y, po["y"])
    return finish(c)


def build_skew(w, stages):
    c = Circuit("SKEW_%d" % stages)
    pi, po = pin_column(c, [("clk", 1), ("clear", 1), ("din", w)], [("dout", w)], x_out=2000 + 1000 * stages)
    c.net("clk", pi["clk"])
    c.net("clear", pi["clear"])
    c.net("st_0", pi["din"])
    for s in range(stages):
        r = c.inst("REG_%d" % w, 1700 + 1000 * s, 300 + 250 * s, "stage%d" % s)
        c.net("clk", r["clk"])
        c.net("clear", r["clear"])
        c.net("st_%d" % s, r["d"])
        c.net("st_%d" % (s + 1), r["q"])
    c.net("st_%d" % stages, po["dout"])
    return finish(c)


def build_control():
    c = Circuit("CONTROL")
    pi, po = pin_column(c, [("clk", 1), ("rst", 1), ("start", 1)], [("t", 4), ("clear", 1), ("done", 1)], x_out=4700)
    comb_t, ends_t = c.splitter(450, 700, "east", 4, 4)
    c.net("t", comb_t)
    for i in range(4):
        c.net(bit("t", i), ends_t[i])
    # clear = start AND NOT run
    n_run = c.not_gate(1100, 200, "not_run")
    g_clear = c.gate("AND", 1700, 200, "and_clear")
    c.net("run", n_run[0])
    c.net("not_run", n_run[1], g_clear[1])
    c.net("start", pi["start"], g_clear[0])
    c.net("clear", g_clear[2], po["clear"])
    # done = (t == 10) = t3 AND (NOT t2) AND t1 AND (NOT t0)
    n_t2 = c.not_gate(1100, 500, "not_t2")
    n_t0 = c.not_gate(1100, 700, "not_t0")
    c.net(bit("t", 2), n_t2[0])
    c.net(bit("t", 0), n_t0[0])
    c.net("nt_2", n_t2[1])
    c.net("nt_0", n_t0[1])
    d_hi = c.gate("AND", 1700, 500, "and_done_hi")
    d_lo = c.gate("AND", 1700, 700, "and_done_lo")
    d_all = c.gate("AND", 2300, 600, "and_done")
    c.net(bit("t", 3), d_hi[0])
    c.net("nt_2", d_hi[1])
    c.net(bit("t", 1), d_lo[0])
    c.net("nt_0", d_lo[1])
    c.net("done_hi", d_hi[2], d_all[0])
    c.net("done_lo", d_lo[2], d_all[1])
    c.net("done", d_all[2], po["done"])
    # busy = run AND NOT done
    n_done = c.not_gate(1100, 1000, "not_done")
    g_busy = c.gate("AND", 1700, 1000, "and_busy")
    c.net("done", n_done[0])
    c.net("not_done", n_done[1], g_busy[1])
    c.net("run", g_busy[0])
    c.net("busy", g_busy[2])
    # run flip-flop: run_next = start OR busy, with a synchronous reset
    g_next = c.gate("OR", 1700, 1300, "or_run_next")
    n_rst = c.not_gate(1100, 1500, "not_rst")
    g_d = c.gate("AND", 2300, 1400, "and_run_d")
    c.net("start", g_next[0])
    c.net("busy", g_next[1])
    c.net("run_next", g_next[2], g_d[0])
    c.net("rst", pi["rst"], n_rst[0])
    c.net("not_rst", n_rst[1], g_d[1])
    c.net("run_d", g_d[2])
    f = c.inst("DFF", 3100, 1400, "run_ff")
    c.net("clk", pi["clk"], f["clk"])
    c.net("run_d", f["D"])
    c.net("run", f["Q"])
    # counter: cleared by clear or rst, counts while busy
    g_cc = c.gate("OR", 2300, 1800, "or_counter_clear")
    c.net("clear", g_cc[0])
    c.net("rst", g_cc[1])
    c.net("counter_clear", g_cc[2])
    ctr = c.inst("COUNTER4", 3900, 1700, "counter")
    c.net("clk", ctr["clk"])
    c.net("counter_clear", ctr["clear"])
    c.net("busy", ctr["en"])
    c.net("t", ctr["q"], po["t"])
    return finish(c)


def build_feeder(w):
    c = Circuit("FEEDER")
    ins = [("clk", 1), ("clear", 1), ("t", 4)] + [("A_row%d" % i, 4 * w) for i in range(4)] + \
          [("B_col%d" % j, 4 * w) for j in range(4)]
    pi, po = pin_column(c, ins, [("a_row_in", 4 * w), ("b_col_in", 4 * w)], x_out=5600)
    dec = c.inst("TDEC4", 1400, 200, "tdec")
    c.net("t", pi["t"], dec["t"])
    c.net("sel", dec["sel"])
    comb_a, ends_a = c.splitter(5100, 600, "west", 4, 4 * w)
    comb_b, ends_b = c.splitter(5100, 1900, "west", 4, 4 * w)
    c.net("clk", pi["clk"])
    c.net("clear", pi["clear"])
    for kind, name_in, ends, base in (("A", "A_row", ends_a, 400), ("B", "B_col", ends_b, 1700)):
        for i in range(4):
            y = base + 300 * i
            sel = c.inst("SELECT4", 2400, y, "sel_%s%d" % (kind, i))
            c.net("sel", sel["sel"])
            c.net("%s_row%d" % (kind, i), pi["%s%d" % (name_in, i)], sel["din"])
            if i == 0:
                c.net("%so_%d" % (kind.lower(), i), sel["y"], ends[i])
            else:
                c.net("%spick_%d" % (kind.lower(), i), sel["y"])
                sk = c.inst("SKEW_%d" % i, 3800, y, "skew_%s%d" % (kind, i))
                c.net("clk", sk["clk"])
                c.net("clear", sk["clear"])
                c.net("%spick_%d" % (kind.lower(), i), sk["din"])
                c.net("%so_%d" % (kind.lower(), i), sk["dout"], ends[i])
    c.net("a_row_in", comb_a, po["a_row_in"])
    c.net("b_col_in", comb_b, po["b_col_in"])
    return finish(c)


def build_systolic(w, acc):
    c = Circuit("SYSTOLIC_4x4")
    ins = [("clk", 1), ("clear", 1), ("a_row_in", 4 * w), ("b_col_in", 4 * w)]
    outs = [("C%d%d" % (i, j), acc, "10unsigned") for i in range(4) for j in range(4)]
    pi, po = pin_column(c, ins, outs, x_out=5600)
    comb_a, ends_a = c.splitter(450, 700, "east", 4, 4 * w)
    comb_b, ends_b = c.splitter(450, 1300, "east", 4, 4 * w)
    c.net("a_row_in", pi["a_row_in"], comb_a)
    c.net("b_col_in", pi["b_col_in"], comb_b)
    c.net("clk", pi["clk"])
    c.net("clear", pi["clear"])
    for i in range(4):
        c.net("a_%d_0" % i, ends_a[i])
    for j in range(4):
        c.net("b_0_%d" % j, ends_b[j])
    for i in range(4):
        for j in range(4):
            p = c.inst("PE", 1700 + 1100 * j, 300 + 400 * i, "PE%d%d" % (i, j))
            c.net("a_%d_%d" % (i, j), p["a_in"])
            c.net("b_%d_%d" % (i, j), p["b_in"])
            c.net("clk", p["clk"])
            c.net("clear", p["clear"])
            if j < 3:
                c.net("a_%d_%d" % (i, j + 1), p["a_out"])
            else:
                c.nc("a_%d" % i, p["a_out"])
            if i < 3:
                c.net("b_%d_%d" % (i + 1, j), p["b_out"])
            else:
                c.nc("b_%d" % j, p["b_out"])
            c.net("C%d%d" % (i, j), p["acc"], po["C%d%d" % (i, j)])
    return finish(c)


def top_ins(w):
    return [("clk", 1), ("rst", 1), ("start", 1)] + [("A_row%d" % i, 4 * w) for i in range(4)] + \
           [("B_col%d" % j, 4 * w) for j in range(4)]


def top_outs(acc):
    return [("done", 1), ("t", 4)] + [("C%d%d" % (i, j), acc, "10unsigned") for i in range(4) for j in range(4)]


def build_top(w, acc):
    c = Circuit("TOP")
    pi, po = pin_column(c, top_ins(w), top_outs(acc), x_out=5400)
    ctl = c.inst("CONTROL", 1400, 300, "control")
    c.net("clk", pi["clk"], ctl["clk"])
    c.net("rst", pi["rst"], ctl["rst"])
    c.net("start", pi["start"], ctl["start"])
    c.net("t", ctl["t"], po["t"])
    c.net("clear", ctl["clear"])
    c.net("done", ctl["done"], po["done"])
    fd = c.inst("FEEDER", 2700, 800, "feeder")
    c.net("clk", fd["clk"])
    c.net("clear", fd["clear"])
    c.net("t", fd["t"])
    for i in range(4):
        c.net("A_row%d" % i, pi["A_row%d" % i], fd["A_row%d" % i])
        c.net("B_col%d" % i, pi["B_col%d" % i], fd["B_col%d" % i])
    c.net("a_row_in", fd["a_row_in"])
    c.net("b_col_in", fd["b_col_in"])
    ar = c.inst("SYSTOLIC_4x4", 4300, 2000, "array")
    c.net("clk", ar["clk"])
    c.net("clear", ar["clear"])
    c.net("a_row_in", ar["a_row_in"])
    c.net("b_col_in", ar["b_col_in"])
    for i in range(4):
        for j in range(4):
            c.net("C%d%d" % (i, j), ar["C%d%d" % (i, j)], po["C%d%d" % (i, j)])
    return finish(c)


def build_case(name, a, b, w, acc, demo=False):
    """Wrapper circuit: the 8 matrix rows/columns are hard-wired Constants.
    demo=True: 'main' with a Clock, LED and Hex Digit Display; otherwise plain input/output pins."""
    cname = "main" if demo else "case_" + name
    c = Circuit(cname)
    if demo:
        pi, po = pin_column(c, [("rst", 1), ("start", 1)],
                            [("done", 1)] + [("C%d%d" % (i, j), acc, "10unsigned") for i in range(4) for j in range(4)],
                            x_out=3600)
    else:
        pi, po = pin_column(c, [("clk", 1), ("rst", 1), ("start", 1)],
                            [("done", 1), ("t", 4)] + [("C%d%d" % (i, j), acc, "10unsigned")
                                                       for i in range(4) for j in range(4)], x_out=3600)
    top = c.inst("TOP", 1900, 400, "top")
    if demo:
        clk = c.comp(LIB_WIRING, (100, 40), "Clock", [("label", "clk")])
        c.net("clk", Port(100, 40, "E", 1), top["clk"])
        # LED on done, Hex Digit Display on t
        c.comp(LIB_IO, (3400, 1900), "LED", [("facing", "west"), ("label", "done_led")])
        c.net("done", top["done"], po["done"], Port(3400, 1900, "W", 1))
        c.comp(LIB_IO, (3400, 2300), "Hex Digit Display", [("label", "t_display")])
        # the hex display input is at (0,0) of the part; its body is above it
        c.net("t", top["t"], Port(3400, 2300, "W", 4))
    else:
        c.net("clk", pi["clk"], top["clk"])
        c.net("done", top["done"], po["done"])
        c.net("t", top["t"], po["t"])
    c.net("rst", pi["rst"], top["rst"])
    c.net("start", pi["start"], top["start"])
    rows = cases.rows_packed(a, w)
    cols = cases.cols_packed(b, w)
    for i in range(4):
        k = c.const(300, 1000 + 200 * i, 4 * w, rows[i])
        c.net("A_row%d" % i, k, top["A_row%d" % i])
        k = c.const(300, 1900 + 200 * i, 4 * w, cols[i])
        c.net("B_col%d" % i, k, top["B_col%d" % i])
    for i in range(4):
        for j in range(4):
            c.net("C%d%d" % (i, j), top["C%d%d" % (i, j)], po["C%d%d" % (i, j)])
    return finish(c)


# =============================================================================
# totals
# =============================================================================
def flat_counts(name, memo):
    if name in memo:
        return memo[name]
    c = [x for x in CIRCUITS if x.name == name][0]
    total = Counter(c.gates)
    for sub, n in c.insts.items():
        t = flat_counts(sub, memo)
        for k, v in t.items():
            total[k] += v * n
    memo[name] = total
    return total


def write_file(path, w, acc):
    lib_block = (
        '  <lib desc="#Wiring" name="0">\n    <tool name="Pin">\n      <a name="appearance" val="classic"/>\n    </tool>\n  </lib>\n'
        '  <lib desc="#Gates" name="1"/>\n  <lib desc="#Memory" name="2"/>\n  <lib desc="#I/O" name="3"/>\n'
        '  <lib desc="#Base" name="4"/>\n')
    toolbar = ('  <toolbar>\n    <tool name="Poke Tool"/>\n    <tool name="Edit Tool"/>\n    <tool name="Wiring Tool"/>\n'
               '    <tool name="Text Tool"/>\n    <sep/>\n    <tool name="Pin"/>\n    <tool name="Pin">\n'
               '      <a name="facing" val="west"/>\n      <a name="type" val="output"/>\n    </tool>\n    <sep/>\n'
               '    <tool name="NOT Gate"/>\n    <tool name="AND Gate"/>\n    <tool name="OR Gate"/>\n'
               '    <tool name="XOR Gate"/>\n    <sep/>\n    <tool name="D Flip-Flop"/>\n  </toolbar>\n')
    text = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<project source="5.0.0" version="1.0">\n'
            '  This file is intended to be loaded by Logisim-evolution v5.0.0(https://github.com/logisim-evolution/).\n\n'
            + lib_block + '  <main name="main"/>\n  <options>\n    <a name="gateUndefined" val="ignore"/>\n'
            '    <a name="simlimit" val="1000"/>\n    <a name="simrand" val="0"/>\n  </options>\n'
            '  <mappings>\n    <tool map="Button2" name="Poke Tool"/>\n    <tool map="Button3" name="Menu Tool"/>\n'
            '    <tool map="Ctrl Button1" name="Menu Tool"/>\n  </mappings>\n' + toolbar)
    for c in CIRCUITS:
        text += c.to_xml()
    text += "</project>\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_all(w, acc):
    SUBS.clear()
    CIRCUITS.clear()
    build_fa()
    build_dff()
    build_adder(w)
    if acc != w:
        build_adder(acc)
    build_mult(w)
    build_reg(w)
    if acc != w:
        build_reg(acc)
    build_reg(4) if w != 4 else None
    build_pe(w, acc)
    build_counter4()
    build_tdec4()
    build_select4(w)
    for s in (1, 2, 3):
        build_skew(w, s)
    build_control()
    build_feeder(w)
    build_systolic(w, acc)
    build_top(w, acc)
    for name in cases.case_names():
        a, b = cases.make_case(name, w)
        build_case(name, a, b, w, acc)
    a, b = cases.make_case("hand_picked", w)
    build_case("hand_picked", a, b, w, acc, demo=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=4)
    ap.add_argument("--acc", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    w = args.w
    acc = args.acc if args.acc else cases.acc_width(w)
    out = args.out or os.path.join(os.path.dirname(HERE), "systolic_gate_level.circ")
    build_all(w, acc)
    write_file(out, w, acc)
    memo = {}
    print("wrote", out, "(W=%d, ACC=%d)" % (w, acc))
    for c in CIRCUITS:
        t = flat_counts(c.name, memo)
        gates = sum(v for k, v in t.items() if k != "DFF")
        print("  %-14s own gates %-4d total 2-input gates %-5d flip-flops %d"
              % (c.name, sum(v for k, v in c.gates.items() if k != "DFF"), gates, t["DFF"]))


if __name__ == "__main__":
    main()
