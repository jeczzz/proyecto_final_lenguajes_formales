# Formal Languages Final Project

## Author
Jorge Enrique Cordoba Zota

## Environment

Verified with Python 3.12.14 on Windows 11.
The Python scripts require Python 3.10 or later and use only its standard
library. No build step is required.

## FIRST, FOLLOW, LL(1) and SLR(1)

Run from the project directory:

```sh
python3 parsers.py
python3 parsers.py --sets
```

On Windows, use `py -3` in place of `python3` if needed. Enter the number
of nonterminals, followed by one production line per nonterminal. The
start symbol is `S`. Alternatives are separated by spaces. Use `e` for
epsilon. The program appends the end marker `$`.

Example session input. There is an empty line before `Q` to close the
parser session.

```text
2
S -> aSb C
C -> c e
T
aacbb
e
acbb

Q
```

Expected recognizer answers are `yes`, `yes`, and `no`. Select `B` to
try the SLR(1) parser with the same strings. When only one parser is
available, enter strings immediately after the grammar classification.

## Syntax-directed definition

```sh
python3 sdd.py
```

Enter one command string per line and finish with an empty line.
The idealized sensor starts at gain 2. Commands `h` and `l` select
gain 4 and 2, respectively. Commands `a` and `b` represent raw signals
8 and 12. Each calibrated reading is the raw signal divided by the
active gain. The final result is the sum of all calibrated readings.

Try `e`, `a`, `hala`, `hbla`, `hx`, and 32 repetitions of `a`.
For valid input, the output includes the annotated tree, the
topological evaluation order, and `S.total`. For `hala`, the
two readings are 2 and 4, and the total is 6.

To test cycle detection:

```sh
python3 sdd.py --circular
```

Enter `a`. This option temporarily makes the initial gain depend on
the total. The reading depends on that gain, so the program prints
`SDD is circular.` and stops.

## Source guide

- `parsers.py`: grammar reader, fixed-point sets, table-driven LL(1)
  parser, LR(0) item collection, and SLR(1) parser.
- `sdd.py`: semantic rule data, generic dependency graph evaluation,
  and the sensor calibration interface.
- `informe_proyecto_final_lf.pdf`: algorithms, generated tables and trace, SDD, and tests.
  The hand-worked example is included in the report.

## Generative AI disclosure

ChatGPT was used as a support tool, it served to search for documentation, clarify concepts and aid with compilation errors along the way.
