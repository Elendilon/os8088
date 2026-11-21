# BZRAIL=1 (Makefile; SPEC.md 130.35): the pathway with the GUARD RAIL test course - applied to path.bbc at build
# time, so the knob's pathway is the shipped one with these lines changed and nothing else.  Pad 0 becomes RAIL (a
# new game rests on it: title, Play Game, Enter); its exit 0 still goes to DOWN (pad 1, TRIAL's until 2026-11-21).  RAIL's exit 1 goes straight
# left to FIRST (pad 6, a dead end, as PEAK is), so every shipped course stays on the map.  FIRST's icon moves with
# it to pad 6; pad 0 shows none.
s/^pad 0 FIRST  22 26$/pad 0 RAIL   22 26\
pad 6 FIRST  20 28/
s/^route 0 1 exit 0  path 22,26 22,21 .*$/&\
route 0 6 exit 1  path 22,26 20,28                  # RAIL's exit 1 -> FIRST (BZRAIL)/
s/^icon 0 icons\/first.bba        -120 376$/icon 6 icons\/first.bba        -184 376/
