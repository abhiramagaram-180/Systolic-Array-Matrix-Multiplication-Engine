# Gate-level Logisim generator

Python 3 standard library only. Run everything from the project root.

| File | Job |
|------|-----|
| `gen_gate_level.py` | Writes `logisim/systolic_gate_level.circ`. Options: `--w 8 --acc 20 --out <file>` for 8-bit inputs. Prints the gate count of every circuit. |
| `check_circuit.py` | Net-connectivity checker. Reads the `.circ` XML itself and checks **every** circuit for shorts (two drivers), undriven inputs, unconnected ports, dangling wires, accidental T-junctions, overlapping wires, tunnel names used once, bit-width mismatches and parts that are not on the allowed list. |
| `verify_gate_level.py` | Bottom-up headless simulation with Logisim-evolution (test vectors): FA, adders, multiplier, flip-flop, registers, PE, counter, decoder, selector, skew lines, control, feeder, array, TOP and every case wrapper, plus a negative control. Needs Logisim-evolution (set `LOGISIM_EXE` if it is not in the default folder). |
| `../make_cases_gate.py` | Test matrices and expected results (shared by the generator and the verifier). |

```bash
python logisim/gate_generator/gen_gate_level.py
python logisim/gate_generator/check_circuit.py
python logisim/gate_generator/verify_gate_level.py            # everything
python logisim/gate_generator/verify_gate_level.py fa mult    # only some tests
```

## A Logisim quirk found while building this

Logisim-evolution 5.0.0 **hangs while loading a file** when a subcircuit instance has a label that equals its circuit's name ignoring upper/lower case (an instance labelled `control` of the circuit `CONTROL`). The headless test runs stalled silently until this was found by bisecting the file. The generator therefore prefixes such labels with `u_` (`u_control`, `u_feeder`, `u_top`), and `check_circuit.py` reports any instance label that equals a circuit name (error `LABEL`).

Second quirk: a Splitter that puts **several bits on one end** (for example 16 bits into 4 lanes of 4 bits) only works when the file lists every bit assignment (`bit0` ... `bit15`, value = end number starting at 0). With just `fanout` and `incoming` the ends read as unknown. Splitters with one bit per end (fanout = incoming) need nothing extra. The generator writes the assignments, and `check_circuit.py` reports a lane splitter without them (error `SPLITTER`).

## Allowed parts

Allowed Logisim parts: NOT / AND / OR / XOR gates; Pin, Constant, Splitter, Tunnel, Clock, Ground; the D Flip-Flop (only inside the circuit `DFF`); LED and Hex Digit Display. The Arithmetic and Plexers libraries, Register, Counter, ROM, RAM, Shift Register and TTL parts are not used (and their libraries are not even loaded in the file).
