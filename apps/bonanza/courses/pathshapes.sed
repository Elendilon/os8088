# BZSHAPES=1 (Makefile; SPEC.md 137.28): the pathway with the FIELD-cell test courses - applied to path.bbc
# at build time, so the knob's pathway is the shipped one with these lines changed and nothing else.
# Pad 0 becomes SHAPE (a new game rests on it: title, Play Game, Enter); its exit 0 still goes to DOWN (pad 1, TRIAL's until 2026-11-21).
# SHAPE's exit 1 goes straight right to PITS (pad 6), its exit 2 straight left to FIRST (pad 7) - both
# dead ends, as PEAK is (FIRST's own finish has no route: DOWN is SHAPE's exit 0, and a route into DOWN
# from the left would share its Left arrow) - so every shipped course stays on the map.  FIRST's icon
# moves with it to pad 7; pad 0 shows none.
s/^pad 0 FIRST  22 26$/pad 0 SHAPE  22 26\
pad 6 PITS   25 23\
pad 7 FIRST  20 28/
s/^route 0 1 exit 0  path 22,26 22,21 .*$/&\
route 0 6 exit 1  gate 24 24  path 22,26 25,23      # SHAPE's exit 1 -> PITS (BZSHAPES)\
route 0 7 exit 2  path 22,26 20,28                  # SHAPE's exit 2 -> FIRST (BZSHAPES)/
s/^icon 0 icons\/first.bba        -120 376$/icon 7 icons\/first.bba        -184 376/
