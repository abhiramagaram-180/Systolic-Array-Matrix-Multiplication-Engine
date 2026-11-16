"""Check that rtl_gate/ is gate-level only (Python 3 standard library only).

Run from the project root:  python scripts/check_gate_only.py

Rules checked in every rtl_gate/*.v except dff.v (the one place flip-flop
behaviour is allowed):
  - no behavioural keywords: always, initial, if, else, case, function, task,
    reg, integer
  - no logic or arithmetic operators outside [ ] index ranges, parameter lists
    and generate-for headers (those are only compile-time numbers):
    + - * / % == != < > <= >= ? ! ~ & | ^ << >>
  - "assign" is only allowed for pure wiring: the right-hand side may only be
    a signal, a bit/part select, a concatenation or a constant
  - gate primitives may only be: and or xor not nand nor
Exit status 1 if anything is found.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = sorted(glob.glob(os.path.join(ROOT, "rtl_gate", "*.v")))
ALLOWED_PRIMITIVES = {"and", "or", "xor", "not", "nand", "nor"}
OTHER_PRIMITIVES = {"buf", "bufif0", "bufif1", "notif0", "notif1", "xnor",
                    "nmos", "pmos", "tran", "pullup", "pulldown"}
KEYWORDS = ["always", "initial", "if", "else", "case", "casex", "casez", "function",
            "task", "reg", "integer", "begin_not_generate"]
problems = []


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def strip_compile_time(text):
    """Remove text that is only compile-time numbers: [..], #(..), for(..), replication counts."""
    text = re.sub(r"`\w+[^\n]*", "", text)                 # `ifdef etc.
    text = re.sub(r"\bgenvar\b[^;]*;", "", text)
    text = re.sub(r"\bfor\s*\([^)]*\)", "", text)
    # parameter lists after the module name: module name #( ... ) (
    text = re.sub(r"#\s*\((?:[^()]|\([^()]*\))*\)", "", text)
    for _ in range(4):                                       # nested [ ... ]
        text = re.sub(r"\[[^\[\]]*\]", "", text)
    text = re.sub(r"\{\s*\([^{}]*\)\s*\{", "{{", text)     # {(N){1'b0}} replication count
    return text


for path in FILES:
    name = os.path.basename(path)
    if name == "dff.v":
        continue
    raw = open(path, encoding="utf-8").read()
    code = strip_compile_time(strip_comments(raw))
    code_ifdef_free = code
    # keywords
    for kw in KEYWORDS:
        if re.search(r"\b%s\b" % kw, code):
            problems.append("%s: behavioural keyword '%s'" % (name, kw))
    # operators
    ops = re.findall(r"==|!=|<=|>=|<<|>>|[+\-*/%<>?!~&|^]", code)
    if ops:
        problems.append("%s: operators outside compile-time text: %s" % (name, sorted(set(ops))))
    # assign statements
    for m in re.finditer(r"\bassign\b([^;]*);", code):
        rhs = m.group(1).split("=", 1)[1] if "=" in m.group(1) else ""
        if not re.fullmatch(r"[\w\s,{}']*", rhs):
            problems.append("%s: assign with more than wiring: %s" % (name, m.group(0).strip()))
    # gate primitives
    for m in re.finditer(r"^\s*(\w+)\s+\w+\s*\(", code, flags=re.M):
        word = m.group(1)
        if word in OTHER_PRIMITIVES:
            problems.append("%s: primitive '%s' is not in the allowed list" % (name, word))

# dff_gates.v is checked like the rest (it uses only nand and not).
# dff.v must be the only file with an always block:
only_dff = [os.path.basename(p) for p in FILES
            if re.search(r"\balways\b", strip_comments(open(p, encoding="utf-8").read()))]
if only_dff != ["dff.v"]:
    problems.append("'always' found in: %s (expected only dff.v)" % only_dff)

if problems:
    print("FAIL: gate-level check")
    for p in problems:
        print("  " + p)
    sys.exit(1)
print("PASS: %d files checked; only dff.v contains behavioural code" % (len(FILES) - 1))
