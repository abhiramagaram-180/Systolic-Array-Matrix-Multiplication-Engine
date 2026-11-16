#!/usr/bin/env python3
"""Net-connectivity checker for a Logisim-evolution .circ file (Python 3 standard library only).

Usage (from the project root):
    python logisim/gate_generator/check_circuit.py                     checks logisim/systolic_gate_level.circ
    python logisim/gate_generator/check_circuit.py some_file.circ [circuit ...]

It reads the XML itself (it does not use the generator) and checks EVERY circuit:
  SHORT        a net bit has two drivers (outputs / input pins / constants ...)
  UNDRIVEN     a net bit has inputs but no driver
  UNUSED       a driven net that nothing reads (allowed only when a tunnel is named nc_...)
  UNCONNECTED  a component port that no wire touches
  DANGLING     a wire end that touches nothing
  TUNNEL       a tunnel name used only once, or used with two different widths
  WIDTH        ports of different bit widths on one net
  T-JUNCTION   a wire end or port lying in the middle of another wire (accidental connection)
  OVERLAP      two wires lying on top of each other
  PART         a component that is not on the allowed list (gate-level rule)
Wire crossings (no connection in Logisim) are only counted.

Port positions (relative to the part) come from the Logisim source code:
    AND/OR gate  in (-50,-20) (-50,20)  out (0,0)     XOR gate in (-60,-20) (-60,20) out (0,0)
    NOT gate     in (-30,0) out (0,0)
    D Flip-Flop  (classic look) CK (-40,0) D (-40,20) Q (0,0) Q-bar (0,20) reset (-10,30) preset (-30,30)
    Splitter     combined end (0,0); other ends at x = +-20 and y = -20*(fanout//2) + 20*i  (spacing 2, centred)
    Pin/Constant/Ground/Clock/Button/LED/Tunnel: port at (0,0); Hex Digit Display: input at (0,0)
    Subcircuit   inputs at (-220, 20k), outputs at (0, 20k), pins sorted top to bottom
The same positions were proved by simulation (verify_gate_level.py): a wrong offset breaks the tests.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILE = os.path.join(os.path.dirname(HERE), "systolic_gate_level.circ")

ALLOWED = {
    "#Wiring": {"Pin", "Constant", "Splitter", "Tunnel", "Clock", "Probe", "Ground", "Power"},
    "#Gates": {"NOT Gate", "AND Gate", "OR Gate", "NAND Gate", "NOR Gate", "XOR Gate", "XNOR Gate"},
    "#Memory": {"D Flip-Flop"},
    "#I/O": {"LED", "Hex Digit Display", "Button"},
}
BOX_W = 220


class Comp:
    def __init__(self, el, libs):
        self.lib = libs.get(el.get("lib")) if el.get("lib") is not None else None
        self.name = el.get("name")
        m = re.match(r"\((-?\d+),(-?\d+)\)", el.get("loc"))
        self.x, self.y = int(m.group(1)), int(m.group(2))
        self.attrs = {a.get("name"): a.get("val") for a in el.findall("a")}
        self.label = self.attrs.get("label", "")


class Circ:
    def __init__(self, el, libs):
        self.name = el.get("name")
        self.comps = [Comp(c, libs) for c in el.findall("comp")]
        self.wires = []
        for w in el.findall("wire"):
            a = tuple(int(v) for v in re.match(r"\((-?\d+),(-?\d+)\)", w.get("from")).groups())
            b = tuple(int(v) for v in re.match(r"\((-?\d+),(-?\d+)\)", w.get("to")).groups())
            self.wires.append((a, b))


def load(path):
    root = ET.parse(path).getroot()
    libs = {l.get("name"): l.get("desc") for l in root.findall("lib")}
    circs = {c.get("name"): Circ(c, libs) for c in root.findall("circuit")}
    return libs, circs


def pin_info(circ):
    """(label, width, is_output, x, y) for every Pin in a circuit."""
    out = []
    for c in circ.comps:
        if c.name == "Pin" and c.lib == "#Wiring":
            out.append((c.label, int(c.attrs.get("width", "1")), c.attrs.get("type") == "output", c.x, c.y))
    return out


def box_ports(circ):
    """Ports of an instance of this circuit relative to its location: [(label, width, is_output, dx, dy)]."""
    pins = pin_info(circ)
    ins = sorted([p for p in pins if not p[2]], key=lambda p: (p[4], p[3]))
    outs = sorted([p for p in pins if p[2]], key=lambda p: (p[4], p[3]))
    res = []
    for k, p in enumerate(ins):
        res.append((p[0], p[1], False, -BOX_W, 20 * k))
    for k, p in enumerate(outs):
        res.append((p[0], p[1], True, 0, 20 * k))
    return res


class Port:
    def __init__(self, x, y, kind, width, desc, comp):
        self.x, self.y, self.kind, self.width, self.desc, self.comp = x, y, kind, width, desc, comp
        # kind: "drv" (drives the net), "snk" (reads the net), "tun" (tunnel), "spl" (splitter end)


def ports_of(c, circs):
    """Return the list of Port objects of a component (None for forbidden parts)."""
    x, y, n = c.x, c.y, c.name
    d = "%s %s@%d,%d" % (n, c.label, x, y)
    P = lambda dx, dy, kind, w, nm: Port(x + dx, y + dy, kind, w, d + "." + nm, c)
    if n == "Pin":
        w = int(c.attrs.get("width", "1"))
        return [P(0, 0, "snk" if c.attrs.get("type") == "output" else "drv", w, "pin")]
    if n == "Constant":
        return [P(0, 0, "drv", int(c.attrs.get("width", "1")), "out")]
    if n in ("Ground", "Power"):
        return [P(0, 0, "drv", int(c.attrs.get("width", "1")), "out")]
    if n in ("Clock", "Button"):
        return [P(0, 0, "drv", 1, "out")]
    if n == "LED":
        return [P(0, 0, "snk", 1, "in")]
    if n == "Hex Digit Display":
        ps = [P(0, 0, "snk", 4, "hex")]
        if c.attrs.get("decimalPoint", "false") == "true":
            ps.append(P(20, 0, "snk", 1, "dp"))
        return ps
    if n == "Tunnel":
        return [P(0, 0, "tun", int(c.attrs.get("width", "1")), "tunnel")]
    if n in ("AND Gate", "OR Gate"):
        return [P(-50, -20, "snk", 1, "a"), P(-50, 20, "snk", 1, "b"), P(0, 0, "drv", 1, "y")]
    if n == "XOR Gate":
        return [P(-60, -20, "snk", 1, "a"), P(-60, 20, "snk", 1, "b"), P(0, 0, "drv", 1, "y")]
    if n == "NOT Gate":
        return [P(-30, 0, "snk", 1, "a"), P(0, 0, "drv", 1, "y")]
    if n == "D Flip-Flop":
        return [P(-40, 0, "snk", 1, "ck"), P(-40, 20, "snk", 1, "d"), P(0, 0, "drv", 1, "q"),
                P(0, 20, "drv", 1, "qbar"), P(-10, 30, "snk", 1, "reset"), P(-30, 30, "snk", 1, "preset")]
    if n == "Splitter":
        fan = int(c.attrs.get("fanout", "2"))
        inc = int(c.attrs.get("incoming", "2"))
        facing = c.attrs.get("facing", "east")
        ex = 20 if facing == "east" else -20
        ps = [P(0, 0, "spl", inc, "combined")]
        per = inc // fan
        for i in range(fan):
            ps.append(P(ex, -20 * (fan // 2) + 20 * i, "spl", per if fan < inc else 1, "end%d" % i))
        return ps
    if c.lib is None and n in circs:
        res = []
        for lab, w, is_out, dx, dy in box_ports(circs[n]):
            res.append(P(dx, dy, "drv" if is_out else "snk", w, lab))
        return res
    return None


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def check_circuit(circ, circs, libs, errors, stats):
    def err(kind, msg):
        errors.append("%s: [%s] %s" % (circ.name, kind, msg))

    # ---- allowed parts
    ports = []
    for c in circ.comps:
        if c.lib is not None:
            allowed = ALLOWED.get(c.lib)
            if allowed is None or c.name not in allowed:
                err("PART", "%s from library %s is not allowed" % (c.name, c.lib))
                continue
            if c.name == "D Flip-Flop" and circ.name != "DFF":
                err("PART", "D Flip-Flop outside the DFF circuit")
        elif c.name not in circs:
            err("PART", "instance of unknown circuit %s" % c.name)
            continue
        else:
            # Logisim-evolution 5.0.0 hangs while loading a file when an instance label equals the
            # name of a circuit (ignoring case), for example instance "control" of circuit CONTROL.
            if c.label and c.label.lower() in [n.lower() for n in circs]:
                err("LABEL", "instance label '%s' equals a circuit name (Logisim hangs when loading this)" % c.label)
        ps = ports_of(c, circs)
        if ps is None:
            err("PART", "cannot model %s" % c.name)
            continue
        ports.extend(ps)

    # ---- wire geometry
    segs = [(a, b) for a, b in circ.wires]
    uf = UF()
    pts = set()
    for a, b in segs:
        uf.union(a, b)
        pts.add(a)
        pts.add(b)

    def inside(p, a, b):
        if a[0] == b[0] == p[0]:
            return min(a[1], b[1]) < p[1] < max(a[1], b[1])
        if a[1] == b[1] == p[1]:
            return min(a[0], b[0]) < p[0] < max(a[0], b[0])
        return False

    port_pts = set((p.x, p.y) for p in ports)
    for (a, b) in segs:
        for q in pts | port_pts:
            if inside(q, a, b):
                err("T-JUNCTION", "point %s lies in the middle of wire %s-%s" % (q, a, b))
    crossings = 0
    for i in range(len(segs)):
        a, b = segs[i]
        for j in range(i + 1, len(segs)):
            c2, d2 = segs[j]
            if a[0] == b[0] and c2[0] == d2[0] and a[0] == c2[0]:                    # both vertical, same x
                lo, hi = max(min(a[1], b[1]), min(c2[1], d2[1])), min(max(a[1], b[1]), max(c2[1], d2[1]))
                if hi > lo:
                    err("OVERLAP", "wires %s-%s and %s-%s overlap" % (a, b, c2, d2))
            elif a[1] == b[1] and c2[1] == d2[1] and a[1] == c2[1]:                  # both horizontal, same y
                lo, hi = max(min(a[0], b[0]), min(c2[0], d2[0])), min(max(a[0], b[0]), max(c2[0], d2[0]))
                if hi > lo:
                    err("OVERLAP", "wires %s-%s and %s-%s overlap" % (a, b, c2, d2))
            else:
                if a[0] == b[0] and c2[1] == d2[1]:
                    v, h = (a, b), (c2, d2)
                elif a[1] == b[1] and c2[0] == d2[0]:
                    v, h = (c2, d2), (a, b)
                else:
                    continue
                if min(h[0][0], h[1][0]) < v[0][0] < max(h[0][0], h[1][0]) and \
                        min(v[0][1], v[1][1]) < h[0][1] < max(v[0][1], v[1][1]):
                    crossings += 1
    stats[circ.name] = {"parts": len(circ.comps), "wires": len(segs), "crossings": crossings}

    # ---- every port must be touched by a wire; every wire end must touch something
    end_count = defaultdict(int)
    for a, b in segs:
        end_count[a] += 1
        end_count[b] += 1
    for p in ports:
        if (p.x, p.y) not in pts:
            err("UNCONNECTED", "%s at (%d,%d)" % (p.desc, p.x, p.y))
    for q, cnt in end_count.items():
        if cnt == 1 and q not in port_pts:
            err("DANGLING", "wire end %s touches nothing" % (q,))

    # ---- nets (positions), then tunnels
    node_ports = defaultdict(list)
    for p in ports:
        if (p.x, p.y) in pts:
            node_ports[uf.find((p.x, p.y))].append(p)
    tun = defaultdict(list)
    for p in ports:
        if p.kind == "tun" and (p.x, p.y) in pts:
            tun[p.comp.label].append(p)
    uf2 = UF()
    for r in node_ports:
        uf2.find(r)
    for label, ps in tun.items():
        widths = set(p.width for p in ps)
        if len(widths) > 1:
            err("TUNNEL", "name %s used with widths %s" % (label, sorted(widths)))
        if len(ps) < 2 and not label.startswith("nc_"):
            err("TUNNEL", "name %s is used only once" % label)
        roots = [uf.find((p.x, p.y)) for p in ps]
        for r in roots[1:]:
            uf2.union(roots[0], r)
    net_of = lambda p: uf2.find(uf.find((p.x, p.y)))
    nets = defaultdict(list)
    for p in ports:
        if (p.x, p.y) in pts:
            nets[net_of(p)].append(p)

    # ---- bit level: splitters connect bus bits to end bits
    bits = UF()
    net_width = {}
    for r, ps in nets.items():
        ws = set(p.width for p in ps if p.kind in ("drv", "snk", "tun"))
        if len(ws) > 1:
            err("WIDTH", "net with ports of widths %s: %s" % (sorted(ws), [p.desc for p in ps][:4]))
        net_width[r] = max(ws) if ws else max(p.width for p in ps)
    for c in circ.comps:
        if c.name != "Splitter":
            continue
        ps = [p for p in ports if p.comp is c and (p.x, p.y) in pts]
        if len(ps) < 2:
            continue
        comb, ends = ps[0], ps[1:]
        fan = len(ends)
        inc = comb.width
        per = inc // fan
        rc = net_of(comb)
        if net_width.get(rc) != inc:
            err("WIDTH", "splitter %s@%d,%d combined end net has width %s, splitter says %d"
                % (c.label, c.x, c.y, net_width.get(rc), inc))
        if fan < inc:
            # lane splitter: Logisim only builds the right bit-to-end table when every bit is assigned in the file
            missing = [b for b in range(inc) if ("bit%d" % b) not in c.attrs]
            wrong = [b for b in range(inc) if ("bit%d" % b) in c.attrs and int(c.attrs["bit%d" % b]) != b // per]
            if missing or wrong:
                err("SPLITTER", "splitter %s@%d,%d (%d bits into %d ends) needs explicit bit assignments "
                    "bit0..bit%d (end = bit // %d); missing %s wrong %s" % (c.label, c.x, c.y, inc, fan, inc - 1, per,
                                                                           missing[:4], wrong[:4]))
        for b in range(inc):
            i, pos = (b, 0) if fan >= inc else (b // per, b % per)
            re_ = net_of(ends[i])
            ew = per if fan < inc else 1
            if net_width.get(re_) != ew:
                err("WIDTH", "splitter %s@%d,%d end %d net has width %s, expected %d"
                    % (c.label, c.x, c.y, i, net_width.get(re_), ew))
            bits.union((rc, b), (re_, pos))
    groups = defaultdict(list)
    for r, ps in nets.items():
        for b in range(net_width[r]):
            for p in ps:
                if p.kind in ("drv", "snk", "tun") and b < p.width:
                    groups[bits.find((r, b))].append((p, b))
    for g, items in groups.items():
        drv = [p.desc for p, b in items if p.kind == "drv"]
        snk = [p.desc for p, b in items if p.kind == "snk"]
        tn = [p for p, b in items if p.kind == "tun"]
        nc = any(p.comp.label.startswith("nc_") for p in tn)
        if len(drv) > 1:
            err("SHORT", "two drivers on one net bit: %s" % sorted(set(drv)))
        if snk and not drv:
            err("UNDRIVEN", "inputs without a driver: %s" % sorted(set(snk))[:4])
        if drv and not snk and not nc:
            err("UNUSED", "output nobody reads: %s" % sorted(set(drv)))

    # ---- instances: widths must match the pins of the referenced circuit (done by the width check above)
    return


def check_hierarchy(circs, errors):
    for name, c in circs.items():
        for k in c.comps:
            if k.lib is None and k.name == name:
                errors.append("%s: [HIERARCHY] circuit contains itself" % name)


def main():
    args = sys.argv[1:]
    path = args[0] if args else DEFAULT_FILE
    only = args[1:]
    libs, circs = load(path)
    errors, stats = [], {}
    check_hierarchy(circs, errors)
    for name, c in circs.items():
        if only and name not in only:
            continue
        check_circuit(c, circs, libs, errors, stats)
    print("checked %d circuits in %s" % (len(stats), os.path.basename(path)))
    print("%-16s %6s %6s %9s" % ("circuit", "parts", "wires", "crossings"))
    for name, s in stats.items():
        print("%-16s %6d %6d %9d" % (name, s["parts"], s["wires"], s["crossings"]))
    if errors:
        print("\nFAIL: %d problem(s)" % len(errors))
        for e in errors[:60]:
            print("  " + e)
        if len(errors) > 60:
            print("  ... %d more" % (len(errors) - 60))
        sys.exit(1)
    print("\nPASS: no shorts, no undriven inputs, no unconnected pins, no dangling wires, no accidental connections")


if __name__ == "__main__":
    main()
